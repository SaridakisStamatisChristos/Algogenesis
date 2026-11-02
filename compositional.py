"""Compositional CEGIS for sequential bounded accumulator loops.

The search prunes observationally equivalent partial programs on training
examples, and verifies candidate ASTs with a separate bounded interpreter.
All correctness claims are limited to the specified finite input domain.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable
from control_flow import IntExpr, Interpreter, Statement, FuelExhausted

@dataclass(frozen=True, order=True)
class Stage:
    count: str
    operation: str
    source: str

@dataclass(frozen=True)
class Program:
    initial: int
    stages: tuple[Stage, ...]

    def ast(self) -> tuple[Statement, ...]:
        accumulator = IntExpr('register', atom='acc')
        statements = [Statement('assign', name='acc', expr=IntExpr('literal', atom=self.initial))]
        for stage in self.stages:
            source = IntExpr('literal', atom=1) if stage.source == 'one' else IntExpr('register', atom=stage.source)
            update = Statement('assign', name='acc', expr=IntExpr(stage.operation, (accumulator, source)))
            statements.append(Statement('repeat', expr=IntExpr('register', atom=stage.count), body=(update,)))
        return tuple(statements)

    def run(self, x: int, y: int, fuel: int = 10000) -> int:
        return Interpreter(fuel=fuel).run(self.ast(), {'x': x, 'y': y})['acc']

    def source(self) -> str:
        lines = [f'acc = {self.initial}']
        for stage in self.stages:
            lines.append(f'repeat({stage.count}): acc = acc {"+" if stage.operation == "add" else "-"} {stage.source}')
        return '\n'.join(lines)

@dataclass(frozen=True)
class Report:
    program: Program | None
    rounds: int
    candidates: int
    verified_cases: int
    counterexamples: tuple[tuple[int, int], ...]
    exhausted: bool

def _stage_delta(stage: Stage, x: int, y: int) -> int:
    count = x if stage.count == 'x' else y
    value = {'x': x, 'y': y, 'one': 1}[stage.source]
    return count * value * (1 if stage.operation == 'add' else -1)

def _predict(program: Program, pair: tuple[int, int]) -> int:
    x, y = pair
    return program.initial + sum(_stage_delta(s, x, y) for s in program.stages)

def _candidates(max_stages: int, examples: tuple[tuple[int, int], ...]):
    stages = tuple(Stage(*args) for args in product(('x','y'), ('add','sub'), ('x','y','one')))
    effects = {}
    for stage in stages:
        sig = tuple(_stage_delta(stage, *pair) for pair in examples)
        effects.setdefault(sig, stage)
    ordered = tuple(sorted(effects.items(), key=lambda item: item[1]))
    for initial in (0,1,-1):
        yield Program(initial, ())
    if max_stages == 0:
        return
    frontier = {tuple(0 for _ in examples): ()}
    seen = set(frontier)
    for _ in range(max_stages):
        next_frontier = {}
        for sig, seq in frontier.items():
            for effect, stage in ordered:
                nxt = tuple(a+b for a,b in zip(sig,effect))
                if nxt in seen or nxt in next_frontier:
                    continue
                next_frontier[nxt] = seq + (stage,)
        for seq in next_frontier.values():
            for initial in (0,1,-1):
                yield Program(initial,seq)
        seen.update(next_frontier)
        frontier = next_frontier

def synthesize(oracle: Callable[[int,int],int], domain: Iterable[int] = range(5),
               *, max_stages=2, max_rounds=30, max_candidates=200000, fuel=10000) -> Report:
    values = tuple(domain)
    if not values or any(type(v) is not int or v < 0 for v in values):
        raise ValueError('domain must be nonempty nonnegative integers')
    if max_stages < 0 or max_stages > 5 or max_rounds < 1 or max_candidates < 1 or fuel < 1:
        raise ValueError('invalid resource budget')
    points = tuple(product(values, repeat=2))
    expected = {}
    for pair in points:
        result = oracle(*pair)
        if type(result) is not int:
            raise TypeError('oracle must return an integer')
        expected[pair] = result
    examples = [points[0]]
    total_candidates = 0
    for rnd in range(1,max_rounds+1):
        winner = None
        for candidate in _candidates(max_stages, tuple(examples)):
            total_candidates += 1
            if total_candidates > max_candidates:
                return Report(None,rnd,total_candidates,len(points),tuple(examples[1:]),True)
            if all(_predict(candidate,pair)==expected[pair] for pair in examples):
                winner = candidate
                break
        if winner is None:
            return Report(None,rnd,total_candidates,len(points),tuple(examples[1:]),False)
        mismatch = None
        for pair in points:
            try:
                actual = winner.run(*pair,fuel=fuel)
            except (ValueError,FuelExhausted):
                actual = None
            if actual != expected[pair]:
                mismatch = pair
                break
        if mismatch is None:
            return Report(winner,rnd,total_candidates,len(points),tuple(examples[1:]),False)
        if mismatch in examples:
            raise AssertionError('candidate violates training examples')
        examples.append(mismatch)
    return Report(None,max_rounds,total_candidates,len(points),tuple(examples[1:]),True)

if __name__ == '__main__':
    for name, oracle in [('xy+x',lambda x,y:x*y+x),
                         ('xy+y',lambda x,y:x*y+y),
                         ('x2+y2',lambda x,y:x*x+y*y)]:
        report=synthesize(oracle)
        print(name,report)
        if report.program:
            print(report.program.source())
