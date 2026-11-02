"""Dependency-free typed integer-expression synthesis with CEGIS.

Domain is finite and explicit: proof claims apply only to the chosen domain.
Search uses observational-equivalence pruning on current counterexamples and
restarts whenever a new counterexample invalidates that abstraction.
"""
from __future__ import annotations
import argparse
import itertools
import json
from dataclasses import dataclass
from typing import Callable

COMMUTATIVE = frozenset({'add', 'min', 'max'})
UNARY = ('neg', 'abs')
BINARY = ('add', 'sub', 'min', 'max')

@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple['Expr', ...] = ()
    value: int | str | None = None

    @property
    def size(self) -> int:
        return 1 + sum(x.size for x in self.args)

    def source(self) -> str:
        if self.op in ('var', 'const'):
            return str(self.value)
        if self.op == 'neg':
            return f'(-{self.args[0].source()})'
        if self.op == 'abs':
            return f'abs({self.args[0].source()})'
        a, b = (x.source() for x in self.args)
        if self.op in ('add', 'sub'):
            return f'({a} {"+" if self.op == "add" else "-"} {b})'
        return f'{self.op}({a}, {b})'

def evaluate(expr: Expr, env: dict[str, int]) -> int:
    if expr.op == 'var':
        return env[str(expr.value)]
    if expr.op == 'const':
        return int(expr.value)
    if expr.op == 'neg':
        return -evaluate(expr.args[0], env)
    if expr.op == 'abs':
        return abs(evaluate(expr.args[0], env))
    a, b = (evaluate(x, env) for x in expr.args)
    return {'add': lambda: a+b, 'sub': lambda: a-b,
            'min': lambda: min(a,b), 'max': lambda: max(a,b)}[expr.op]()

def expression_search(examples: list[tuple[tuple[int, ...], int]],
                      variables=('x', 'y'), constants=(0, 1), max_size=7,
                      max_semantics=100000) -> tuple[Expr | None, int]:
    """Enumerate ASTs by node count, keeping one representative per signature.

    A signature is the vector of outputs on the supplied examples. Since all
    operators are pure and total, equivalent signatures are substitutable.
    """
    if not examples or max_size < 1 or max_semantics < 1:
        raise ValueError('nonempty examples and positive budgets required')
    if any(len(inp) != len(variables) for inp, _ in examples):
        raise ValueError('example arity mismatch')
    inputs = [dict(zip(variables, inp)) for inp, _ in examples]
    goal = tuple(output for _, output in examples)
    levels: dict[int, dict[tuple[int, ...], Expr]] = {}
    count = 0

    def offer(level: dict, sig: tuple[int, ...], expr: Expr):
        nonlocal count
        if sig in level:
            return
        if any(sig in levels[k] for k in levels):
            return
        if count >= max_semantics:
            raise RuntimeError('semantic-state budget exhausted')
        level[sig] = expr
        count += 1

    for size in range(1, max_size+1):
        current: dict[tuple[int, ...], Expr] = {}
        if size == 1:
            for v in variables:
                e = Expr('var', value=v)
                offer(current, tuple(evaluate(e, inp) for inp in inputs), e)
            for c in constants:
                e = Expr('const', value=c)
                offer(current, tuple(c for _ in inputs), e)
        else:
            for op in UNARY:
                for sig, sub in levels.get(size-1, {}).items():
                    result = tuple(-v if op == 'neg' else abs(v) for v in sig)
                    offer(current, result, Expr(op, (sub,)))
            for left_size in range(1, size-1):
                right_size = size-1-left_size
                for ls, le in levels.get(left_size, {}).items():
                    for rs, re in levels.get(right_size, {}).items():
                        for op in BINARY:
                            if op in COMMUTATIVE and (left_size, ls) > (right_size, rs):
                                continue
                            if op == 'add':
                                result = tuple(a+b for a,b in zip(ls,rs))
                            elif op == 'sub':
                                result = tuple(a-b for a,b in zip(ls,rs))
                            elif op == 'min':
                                result = tuple(min(a,b) for a,b in zip(ls,rs))
                            else:
                                result = tuple(max(a,b) for a,b in zip(ls,rs))
                            offer(current, result, Expr(op,(le,re)))
        if goal in current:
            return current[goal], count
        levels[size] = current
    return None, count

@dataclass(frozen=True)
class SynthesisResult:
    expression: Expr | None
    rounds: int
    evaluations: int
    counterexamples: tuple[tuple[int, ...], ...]
    verified: bool
    domain_size: int

    def as_dict(self):
        return {'expression': self.expression.source() if self.expression else None,
                'ast_nodes': self.expression.size if self.expression else None,
                'rounds': self.rounds, 'evaluations': self.evaluations,
                'counterexamples': [list(x) for x in self.counterexamples],
                'verified': self.verified, 'domain_size': self.domain_size,
                'verification_scope': 'exhaustive finite domain only'}

def synthesize(oracle: Callable[..., int], variables=('x','y'), domain=range(-3,4),
               max_size=7, max_rounds=100, max_semantics=100000) -> SynthesisResult:
    if not variables or not domain or max_rounds < 1:
        raise ValueError('invalid synthesis parameters')
    points = list(itertools.product(domain, repeat=len(variables)))
    if not points:
        raise ValueError('empty domain')
    selected = [points[0]]
    seen = set(selected)
    evaluations = 0
    for round_number in range(1, max_rounds+1):
        examples = [(p, oracle(*p)) for p in selected]
        expr, work = expression_search(examples, variables, max_size=max_size,
                                       max_semantics=max_semantics)
        evaluations += work
        if expr is None:
            return SynthesisResult(None, round_number, evaluations, tuple(selected[1:]), False, len(points))
        mismatch = next((p for p in points if evaluate(expr, dict(zip(variables,p))) != oracle(*p)), None)
        if mismatch is None:
            return SynthesisResult(expr, round_number, evaluations, tuple(selected[1:]), True, len(points))
        if mismatch in seen:
            raise AssertionError('counterexample-guided search failed to honor examples')
        selected.append(mismatch)
        seen.add(mismatch)
    return SynthesisResult(None, max_rounds, evaluations, tuple(selected[1:]), False, len(points))

TASKS = {
    'absdiff': lambda x,y: abs(x-y),
    'maximum': lambda x,y: max(x,y),
    'minimum': lambda x,y: min(x,y),
    'sum': lambda x,y: x+y,
    'distance_to_zero': lambda x,y: abs(x),
}

def main():
    p = argparse.ArgumentParser(description='Finite-domain CEGIS integer program synthesizer')
    p.add_argument('--task', choices=sorted(TASKS), default='absdiff')
    p.add_argument('--bound', type=int, default=3)
    p.add_argument('--max-size', type=int, default=7)
    p.add_argument('--max-rounds', type=int, default=100)
    args = p.parse_args()
    if not 0 <= args.bound <= 20:
        p.error('bound must be between 0 and 20')
    result = synthesize(TASKS[args.task], domain=range(-args.bound,args.bound+1),
                        max_size=args.max_size, max_rounds=args.max_rounds)
    print(json.dumps({'task':args.task, **result.as_dict()},indent=2))

if __name__ == '__main__':
    main()
