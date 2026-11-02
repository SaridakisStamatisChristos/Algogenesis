"""v2.8 bounded, proof-guided SyGuS synthesis from ORIGINAL constraints.

Unlike the pointwise-label CEGIS search, this finite enumerator never assumes
that a specification has one permitted output per input. It constructs a
small, deterministic candidate grammar and asks an external SMT solver to
disprove every original SyGuS constraint. Only verified UNSAT is success.

Supports one or two grammar-free integer synth-funs sharing <=2 integer
arguments, plus source-side helper functions understood by the external
checker. This is deliberately NOT a complete or fair SyGuS solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from time import perf_counter
import re
import shutil

from sygus_clia import Unsupported, parse_sexpressions
from sygus_general_checker import check_external_solution

_SYMBOL = re.compile(r"[A-Za-z_][A-Za-z_0-9.\-]*\Z", re.ASCII)


@dataclass(frozen=True)
class SearchResult:
    status: str
    solution: str | None
    checked: int
    considered: int
    elapsed_seconds: float
    reason: str


def _signatures(source: str):
    roots = parse_sexpressions(source)
    functions = []
    for cmd in roots:
        if not isinstance(cmd, list) or not cmd:
            raise Unsupported('malformed SyGuS source')
        if cmd[0] != 'synth-fun':
            continue
        if (len(cmd) != 4 or cmd[3] != 'Int' or
                not isinstance(cmd[2], list)):
            raise Unsupported('requires grammar-free Int synth-fun')
        if not isinstance(cmd[1], str) or not _SYMBOL.fullmatch(cmd[1]):
            raise Unsupported('invalid synthesis function name')
        args = []
        for entry in cmd[2]:
            if (not isinstance(entry, list) or len(entry) != 2 or
                    entry[1] != 'Int' or not isinstance(entry[0], str) or
                    not _SYMBOL.fullmatch(entry[0])):
                raise Unsupported('requires integer synth-fun arguments')
            args.append(entry[0])
        if len(set(args)) != len(args) or not 1 <= len(args) <= 2:
            raise Unsupported('only 1 or 2 distinct arguments supported')
        functions.append((cmd[1], tuple(args)))
    if not 1 <= len(functions) <= 2:
        raise Unsupported('supports one or two synthesis targets')
    if len(set(name for name, _ in functions)) != len(functions):
        raise Unsupported('duplicate synthesis target')
    if len({names for _, names in functions}) != 1:
        raise Unsupported('multiple synthesis functions must share argument names')
    return tuple(functions)


def _form_candidates(names: tuple[str, ...]):
    """Enumerate a bounded grammar; no input-benchmark-name or oracle lookup."""
    x = names[0]
    y = names[1] if len(names) == 2 else None
    leaves = ['0', '1', '2', '(- 1)', x]
    if y is not None:
        leaves.append(y)
    seen: set[str] = set()

    def emit(v):
        if v not in seen:
            seen.add(v)
            return v
        return None

    for leaf in leaves:
        term = emit(leaf)
        if term is not None:
            yield term
    # Elementary linear arithmetic expressions.
    forms = [f'(- {x})', f'(+ {x} 1)', f'(- {x} 1)']
    if y is not None:
        forms += [f'(+ {x} {y})', f'(- {x} {y})',
                  f'(- {y} {x})', f'(+ {y} 1)', f'(- {y} 1)']
    for expr in forms:
        term = emit(expr)
        if term is not None:
            yield term

    guards = []
    if y is not None:
        guards += [f'(= {x} {y})', f'(< {x} {y})',
                   f'(<= {x} {y})', f'(< {y} {x})']
    guards += [f'(= {x} 0)', f'(< {x} 0)', f'(<= {x} 0)']
    if y is not None:
        guards += [f'(= {y} 0)', f'(< {y} 0)', f'(<= {y} 0)']
    # Equivalent-on-samples pruning is deliberately NOT performed. Under
    # universally quantified source constraints with shifted function calls,
    # finite observational equivalence need not preserve correctness.
    branch_leaves = ['0', '1', '2', x]
    if y is not None:
        branch_leaves.append(y)
    pairs = [(a, b) for a, b in product(branch_leaves, repeat=2) if a != b]
    for guard in guards:
        for yes, no in pairs:
            term = emit(f'(ite {guard} {yes} {no})')
            if term is not None:
                yield term


def _define(name, names, expr):
    params = ' '.join(f'({n} Int)' for n in names)
    return f'(define-fun {name} ({params}) Int {expr})'


def _candidate_sources(signatures):
    names = signatures[0][1]
    terms = tuple(_form_candidates(names))
    if len(signatures) == 1:
        for body in terms:
            yield _define(signatures[0][0], names, body)
        return
    left, right = signatures[0][0], signatures[1][0]
    # Start with shared programs: important for relational invariants
    # but not a benchmark-specific rule or an assumption of equality.
    for body in terms:
        yield _define(left, names, body) + '\n' + _define(right, names, body)
    # Bounded joint synthesis; enumerate distinct functions without
    # artificially fixing one function to zero.
    for a, b in product(terms[:20], repeat=2):
        if a != b:
            yield _define(left, names, a) + '\n' + _define(right, names, b)


def synthesize_verified(source: str, *, max_candidates: int = 160,
                        max_wall_seconds: float = 3.25,
                        solver_timeout_seconds: float = 0.35) -> SearchResult:
    """Return success only after UNSAT of negated original specifications.

    Search bounds are distinct from correctness: exhaustion/timeout means
    no solution FOUND in this small grammar/budget, NOT unsatisfiability.
    """
    if (type(max_candidates) is not int or not 1 <= max_candidates <= 10000 or
            type(max_wall_seconds) not in (int, float) or
            not 0 < max_wall_seconds <= 120 or
            type(solver_timeout_seconds) not in (int, float) or
            not 0 < solver_timeout_seconds <= 30):
        raise ValueError('invalid search budgets')
    sigs = _signatures(source)
    if not shutil.which('z3'):
        return SearchResult('unavailable', None, 0, 0, 0.0, 'Z3 is not installed')
    start = perf_counter()
    checked = considered = 0
    inconclusive = 0
    for candidate in _candidate_sources(sigs):
        elapsed = perf_counter() - start
        if considered >= max_candidates:
            return SearchResult('budget_exhausted', None, checked, considered,
                                elapsed, 'candidate budget reached')
        if elapsed >= max_wall_seconds:
            return SearchResult('budget_exhausted', None, checked, considered,
                                elapsed, 'wall-clock search budget reached')
        considered += 1
        remaining = max_wall_seconds - elapsed
        verdict = check_external_solution(
            source, candidate,
            timeout_seconds=min(solver_timeout_seconds, remaining))
        checked += 1
        if verdict.status == 'proved':
            return SearchResult('proved', candidate, checked, considered,
                                perf_counter() - start,
                                'external Z3 UNSAT on all original constraints')
        if verdict.status != 'counterexample':
            inconclusive += 1
            if verdict.status in ('error', 'unavailable'):
                return SearchResult('unverified', None, checked, considered,
                                    perf_counter() - start,
                                    'external checker error: ' + verdict.detail[:150])
    return SearchResult('not_found_in_grammar' if not inconclusive else
                        'unverified', None, checked, considered,
                        perf_counter() - start,
                        f'exhausted finite grammar; inconclusive={inconclusive}')
