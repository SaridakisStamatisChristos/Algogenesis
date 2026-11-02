"""Finite-domain synthesis of dynamic-loop programs, with explicit resource bounds.

No input specialization: the same immutable AST executes for every input.
Proof status: finite-domain exhaustive only. No claim of unbounded correctness.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Callable
from control_flow import IntExpr, Statement, Interpreter, FuelExhausted


def reg(name: str) -> IntExpr:
    return IntExpr('register', atom=name)


def lit(value: int) -> IntExpr:
    return IntExpr('literal', atom=value)


@dataclass(frozen=True)
class DynamicProgram:
    initial: int
    count: str
    update: str
    operation: str

    def ast(self) -> tuple[Statement, ...]:
        count = reg(self.count)
        update = reg(self.update)
        acc = reg('acc')
        return (Statement('assign', name='acc', expr=lit(self.initial)),
                Statement('repeat', expr=count, body=(
                    Statement('assign', name='acc', expr=IntExpr(self.operation, (acc, update))),
                )))

    def run(self, x: int, y: int, fuel: int = 1000) -> int:
        return Interpreter(fuel=fuel).run(self.ast(), {'x': x, 'y': y})['acc']

    def describe(self) -> str:
        return f'acc={self.initial}; repeat({self.count}): acc={self.operation}(acc,{self.update})'


@dataclass(frozen=True)
class SynthesisReport:
    program: DynamicProgram | None
    rounds: int
    counterexamples: tuple[tuple[int, int], ...]
    verified_cases: int
    evaluations: int
    exhausted: bool


def synthesize(oracle: Callable[[int,int],int], domain=range(7), *, max_rounds=100,
               fuel=1000) -> SynthesisReport:
    values = tuple(domain)
    if not values or any(type(v) is not int or v < 0 for v in values):
        raise ValueError('domain must contain nonnegative integers')
    if max_rounds < 1 or fuel < 1:
        raise ValueError('invalid resource limit')
    cases = tuple(product(values, repeat=2))
    # Snapshot the oracle once; avoid re-evaluating side-effectful oracles.
    expected = {p: oracle(*p) for p in cases}
    if any(type(v) is not int for v in expected.values()):
        raise TypeError('oracle must return integers')
    candidates = tuple(DynamicProgram(a,c,u,op) for a,c,u,op in product(
        (0,1,-1), ('x','y'), ('x','y'), ('add','sub')))
    examples = [cases[0]]
    evaluations = 0
    for rnd in range(1,max_rounds+1):
        winner = None
        for candidate in candidates:
            good = True
            for pair in examples:
                evaluations += 1
                try:
                    actual = candidate.run(*pair, fuel=fuel)
                except (FuelExhausted, ValueError):
                    good = False
                    break
                if actual != expected[pair]:
                    good = False
                    break
            if good:
                winner = candidate
                break
        if winner is None:
            return SynthesisReport(None,rnd,tuple(examples[1:]),len(cases),evaluations,False)
        bad = None
        for pair in cases:
            evaluations += 1
            try:
                actual = winner.run(*pair, fuel=fuel)
            except (FuelExhausted, ValueError):
                actual = None
            if actual != expected[pair]:
                bad = pair
                break
        if bad is None:
            return SynthesisReport(winner,rnd,tuple(examples[1:]),len(cases),evaluations,False)
        if bad in examples:
            raise AssertionError('counterexample was already a training example')
        examples.append(bad)
    return SynthesisReport(None,max_rounds,tuple(examples[1:]),len(cases),evaluations,True)


if __name__ == '__main__':
    print(synthesize(lambda x,y:x*y))
