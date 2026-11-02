"""Exact structural CLIA synthesis for externally specified max of 2..6 Int inputs.

This is a specialized decision-tree construction, NOT general algorithm
discovery. The recognizer is deliberately narrow: it must match every
upper-bound constraint AND a disjunction asserting that the output equals
one of the inputs. Therefore the unique valid function is maximum.
Soundness is independently checked with Z3 by the benchmark runner.
"""
from __future__ import annotations

from dataclasses import dataclass

from sygus_clia import Affine, Guard, Problem, Tree, Unsupported, parse_problem


@dataclass(frozen=True)
class StructuralResult:
    tree: Tree
    rule: str
    input_count: int
    nodes: int


def _equal(expr, left, right) -> bool:
    return expr == ['=', left, right] or expr == ['=', right, left]


def _flatten_or(expr):
    if not isinstance(expr, list) or not expr:
        return (expr,)
    if expr[0] != 'or':
        return (expr,)
    if len(expr) < 2:
        raise Unsupported('empty disjunction')
    return tuple(item for child in expr[1:] for item in _flatten_or(child))


def _recognize_max(problem: Problem) -> bool:
    names = problem.variables
    n = len(names)
    if not 2 <= n <= 6 or len(problem.constraints) != n + 1:
        return False
    call = [problem.name, *names]

    # Bind each input from the exact original source. Neither comments,
    # function name nor training examples can trigger this rule.
    bounds = set()
    other = []
    for form in problem.constraints:
        found = False
        for index, name in enumerate(names):
            if form == ['>=', call, name] or form == ['<=', name, call]:
                if index in bounds:
                    return False
                bounds.add(index)
                found = True
                break
        if not found:
            other.append(form)
    if len(bounds) != n or len(other) != 1:
        return False
    alternatives = _flatten_or(other[0])
    if len(alternatives) != n:
        return False
    used = set()
    for item in alternatives:
        found = next((i for i, name in enumerate(names)
                      if _equal(item, name, call)), None)
        if found is None or found in used:
            return False
        used.add(found)
    return len(used) == n


def _variable(n: int, i: int) -> Tree:
    return Tree(leaf=Affine(tuple(int(j == i) for j in range(n))))


def _append_challenger(tree: Tree, challenger: int, arity: int) -> Tree:
    """Symbolically split each incumbent-result leaf against new variable.

    This is expansion to the existing Guard/Tree grammar: guards compare
    variables, never recursively computed expressions. Number of leaf paths
    is exactly 2^(n-1), so this route is capped at n<=6.
    """
    if tree.leaf is not None:
        coeffs = tree.leaf.coefficients
        incumbent = next((i for i,c in enumerate(coeffs) if c == 1), None)
        if (incumbent is None or sum(coeffs) != 1
                or tree.leaf.constant != 0
                or any(c not in (0,1) for c in coeffs)):
            raise ValueError('internal champion must be an input variable')
        return Tree(guard=Guard(incumbent, challenger, '<'),
                    yes=_variable(arity, challenger),
                    no=_variable(arity, incumbent))
    return Tree(guard=tree.guard,
                yes=_append_challenger(tree.yes, challenger, arity),
                no=_append_challenger(tree.no, challenger, arity))


def synthesize_structural_max(problem: Problem) -> StructuralResult | None:
    """Return a candidate only for the exactly matched max contract.

    The contract itself entails f(x) = max_i x_i over a total order.
    Run an independent solver to verify the emitted candidate as well.
    """
    if not _recognize_max(problem):
        return None
    n = len(problem.variables)
    tree = _variable(n, 0)
    for index in range(1, n):
        tree = _append_challenger(tree, index, n)
    return StructuralResult(tree, 'exact-max-contract', n, tree.nodes())


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    from sygus_clia import output, Result
    from sygus_smt_bridge import check_with_smt
    parser = argparse.ArgumentParser()
    parser.add_argument('benchmark', type=Path)
    parser.add_argument('--solver', choices=('z3','cvc5','auto'), default='auto')
    args = parser.parse_args()
    text = args.benchmark.read_text(encoding='utf-8')
    problem = parse_problem(text)
    candidate = synthesize_structural_max(problem)
    if candidate is None:
        raise SystemExit('unsupported: benchmark is not the exact max contract')
    dummy = Result(candidate.tree, 0, 0, 0, None, 'candidate')
    solution = output(problem, dummy)
    verdict = check_with_smt(text, solution, solver=args.solver)
    print(f'{candidate.rule}: {candidate.nodes} nodes, {verdict.solver}: {verdict.status}')
    if verdict.status != 'proved':
        raise SystemExit(1)
