"""Independent SMT-LIB validity check for AlgoGenesis' restricted SyGuS-CLIA tasks.

An UNSAT result for the negated conjunction of the ORIGINAL constraints is
an independent solver check of the candidate. This module never interprets
'unknown', solver absence, timeout or malformed output as a proof. External
SMT solvers are optional; AlgoGenesis itself remains dependency-free.

The input subset and candidate AST are validated before SMT-LIB emission.
This is not a complete SyGuS-IF parser or a formally verified encoder.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns
import argparse
import json
import re
import shutil
import subprocess

from sygus_clia import (Affine, Guard, Problem, Tree, Unsupported,
                        parse_problem, parse_sexpressions, output, synthesize)
from sygus_solution_checker import parse_candidate

_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z_0-9.\-]*\Z", re.ASCII)
_INT = re.compile(r"-?[0-9]+\Z", re.ASCII)
_RESERVED = frozenset(('true', 'false', 'Int', 'Bool', 'and', 'or', 'not',
                       'ite', 'let', 'as', 'forall', 'exists', 'mod', 'div'))


def _symbol(name: str) -> str:
    if not isinstance(name, str) or not _SYMBOL.fullmatch(name) or name in _RESERVED:
        raise Unsupported('unsupported SMT-LIB symbol')
    return name


def _integer(value: int) -> str:
    if type(value) is not int:
        raise Unsupported('integer coefficients required')
    return str(value) if value >= 0 else f'(- {-value})'


def _leaf(leaf: Affine, names: tuple[str, ...]) -> str:
    if len(leaf.coefficients) != len(names):
        raise Unsupported('candidate coefficient arity mismatch')
    parts = []
    if leaf.constant:
        parts.append(_integer(leaf.constant))
    for coeff, name in zip(leaf.coefficients, names):
        if type(coeff) is not int:
            raise Unsupported('integer coefficient required')
        if coeff == 1:
            parts.append(name)
        elif coeff == -1:
            parts.append(f'(- {name})')
        elif coeff > 1:
            parts.append(f'(* {coeff} {name})')
        elif coeff < -1:
            parts.append(f'(- (* {-coeff} {name}))')
    if not parts:
        return '0'
    return parts[0] if len(parts) == 1 else f'(+ {" ".join(parts)})'


def _tree_source(tree: Tree, names: tuple[str, ...]) -> str:
    if tree.leaf is not None:
        if tree.guard is not None or tree.yes is not None or tree.no is not None:
            raise Unsupported('malformed candidate leaf')
        return _leaf(tree.leaf, names)
    if not isinstance(tree.guard, Guard) or tree.yes is None or tree.no is None:
        raise Unsupported('malformed candidate branch')
    if tree.guard.op not in ('<', '<='):
        raise Unsupported('unsupported candidate guard')
    left = '0' if tree.guard.left is None else names[tree.guard.left]
    right = '0' if tree.guard.right is None else names[tree.guard.right]
    return (f'(ite ({tree.guard.op} {left} {right}) '
            f'{_tree_source(tree.yes, names)} {_tree_source(tree.no, names)})')


def _spec(expr, expected: str, problem: Problem) -> str:
    """Type-check and serialize ONLY the supported source constraint language."""
    if isinstance(expr, str):
        if expected == 'Int':
            if expr in problem.variables:
                return expr
            if _INT.fullmatch(expr):
                return _integer(int(expr))
        if expected == 'Bool' and expr in ('true', 'false'):
            return expr
        raise Unsupported('unknown or ill-typed specification atom')
    if not isinstance(expr, list) or not expr or not isinstance(expr[0], str):
        raise Unsupported('malformed specification expression')
    op, *args = expr
    if expected == 'Int':
        if op == problem.name and len(args) == len(problem.variables):
            return f'({op} {" ".join(_spec(a, "Int", problem) for a in args)})'
        if op in ('+', '-') and ((op == '+' and len(args) >= 1) or
                              (op == '-' and len(args) in (1, 2))):
            return f'({op} {" ".join(_spec(a, "Int", problem) for a in args)})'
        raise Unsupported('nonlinear or ill-typed arithmetic in specification')
    if expected == 'Bool':
        if op in ('=', '<', '<=', '>', '>=') and len(args) == 2:
            return f'({op} {" ".join(_spec(a, "Int", problem) for a in args)})'
        if op in ('and', 'or') and args:
            return f'({op} {" ".join(_spec(a, "Bool", problem) for a in args)})'
        if op == 'not' and len(args) == 1:
            return f'(not {_spec(args[0], "Bool", problem)})'
        if op == '=>' and len(args) == 2:
            return f'(=> {" ".join(_spec(a, "Bool", problem) for a in args)})'
        raise Unsupported('ill-typed Boolean expression in specification')
    raise AssertionError('internal sort error')


def build_smt_query(source: str, solution: str) -> str:
    """Translate a checked solution into a validity query over ALL integers.

    UNSAT for this query means no input assignment violates ANY original
    constraint. SAT means at least one counterexample exists.
    """
    problem = parse_problem(source)
    names = tuple(_symbol(x) for x in problem.variables)
    fn = _symbol(problem.name)
    if fn in names:
        raise Unsupported('function name collides with an input variable')
    tree = parse_candidate(problem, solution)
    body = _tree_source(tree, names)
    constraints = tuple(_spec(form, 'Bool', problem) for form in problem.constraints)
    args = ' '.join(f'({name} Int)' for name in names)
    lines = ['(set-logic QF_LIA)',
             f'(define-fun {fn} ({args}) Int {body})']
    lines.extend(f'(declare-const {name} Int)' for name in names)
    conjunction = (constraints[0] if len(constraints) == 1 else
                   f'(and {" ".join(constraints)})')
    lines.extend((f'(assert (not {conjunction}))', '(check-sat)', '(exit)'))
    return '\n'.join(lines) + '\n'


@dataclass(frozen=True)
class SMTCheck:
    status: str        # proved, counterexample, unknown, unavailable, timeout, error
    solver: str
    elapsed_ns: int
    detail: str


def check_with_smt(source: str, solution: str, *, solver: str = 'auto',
                   timeout_seconds: float = 30.0) -> SMTCheck:
    """Invoke Z3 or cvc5 without shell expansion; never promote non-UNSAT."""
    if solver not in ('auto', 'z3', 'cvc5'):
        raise ValueError('solver must be auto, z3 or cvc5')
    if (isinstance(timeout_seconds, bool) or
            not isinstance(timeout_seconds, (int, float)) or
            not 0 < timeout_seconds <= 3600):
        raise ValueError('timeout must be positive and at most 3600 seconds')
    # Validate first: invalid source/candidates are never dispatched to a solver.
    query = build_smt_query(source, solution)
    chosen = (next((name for name in ('z3', 'cvc5') if shutil.which(name)), None)
              if solver == 'auto' else solver)
    if not chosen or not shutil.which(chosen):
        return SMTCheck('unavailable', chosen or solver, 0,
                        'no supported external SMT solver executable found')
    argv = ([chosen, '-in', '-smt2'] if chosen == 'z3' else
            [chosen, '--lang=smt2'])
    start = perf_counter_ns()
    try:
        result = subprocess.run(argv, input=query, capture_output=True,
                                text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return SMTCheck('timeout', chosen, perf_counter_ns() - start,
                        'external solver exceeded timeout')
    except FileNotFoundError:
        return SMTCheck('unavailable', chosen, perf_counter_ns() - start,
                        'external solver was not found at execution')
    except OSError as exc:
        return SMTCheck('error', chosen, perf_counter_ns() - start,
                        f'external solver launch failed: {type(exc).__name__}')
    elapsed = perf_counter_ns() - start
    tokens = result.stdout.strip().splitlines()
    if result.returncode != 0 or len(tokens) != 1:
        return SMTCheck('error', chosen, elapsed,
                        'solver exited nonzero or returned malformed output')
    status = tokens[0].strip()
    if status == 'unsat':
        return SMTCheck('proved', chosen, elapsed,
                        'independent SMT refutation of a violated original constraint')
    if status == 'sat':
        return SMTCheck('counterexample', chosen, elapsed,
                        'at least one violating integer assignment exists')
    if status == 'unknown':
        return SMTCheck('unknown', chosen, elapsed, 'solver returned unknown')
    return SMTCheck('error', chosen, elapsed, 'unrecognized solver response')


def main() -> int:
    p = argparse.ArgumentParser(description='External SMT check of restricted SyGuS solutions')
    p.add_argument('benchmark', type=Path, nargs='?')
    p.add_argument('--solution', type=Path, help='define-fun text file; otherwise synthesize')
    p.add_argument('--solver', choices=('auto', 'z3', 'cvc5'), default='auto')
    p.add_argument('--timeout', type=float, default=30.0)
    p.add_argument('--all', action='store_true', help='four pinned SyGuS examples')
    args = p.parse_args()
    if args.all and (args.benchmark is not None or args.solution is not None):
        p.error('--all cannot be combined with a benchmark or solution file')
    if not args.all and args.benchmark is None:
        p.error('a benchmark or --all is required')
    names = ('max2.sl', 'max3.sl', 'max4.sl', 'diff.sl')
    sources = ([Path(__file__).resolve().parent/'benchmarks'/'sygus_clia'/n
                for n in names] if args.all else [args.benchmark])
    success = True
    for filename in sources:
        source = filename.read_text(encoding='utf-8')
        if args.solution is None:
            problem = parse_problem(source)
            synthesis = synthesize(problem, max_depth=3)
            if synthesis.tree is None:
                print(json.dumps({'benchmark': str(filename), 'status': synthesis.status}))
                success = False
                continue
            solution = output(problem, synthesis)
        else:
            solution = args.solution.read_text(encoding='utf-8')
        result = check_with_smt(source, solution, solver=args.solver,
                                timeout_seconds=args.timeout)
        print(json.dumps({'benchmark': str(filename), **result.__dict__}))
        success = success and result.status == 'proved'
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
