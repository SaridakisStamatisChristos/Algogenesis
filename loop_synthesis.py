"""Counterexample-guided synthesis of bounded-loop accumulator programs.

A deliberately finite DSL: initial accumulator, repeated update, output register.
Candidate programs have fixed repeat counts and integer expressions; exhaustive
verification establishes correctness only on the supplied finite domain.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from typing import Callable
from control_flow import IntExpr, Statement, Interpreter, FuelExhausted

@dataclass(frozen=True)
class LoopCandidate:
    initial: int
    update: str
    iterations: str
    def program(self, x: int, y: int) -> tuple[Statement, ...]:
        count = {'x': x, 'y': y, 'min': min(x,y), 'max': max(x,y)}[self.iterations]
        if count < 0: raise ValueError('negative iteration count')
        a = IntExpr('register',atom='acc')
        b = IntExpr('register',atom='x' if self.update.endswith('x') else 'y')
        op = 'add' if self.update.startswith('add') else 'sub'
        return (Statement('assign',name='acc',expr=IntExpr('literal',atom=self.initial)),
                Statement('repeat',count=count,body=(Statement('assign',name='acc',expr=IntExpr(op,(a,b))),)))
    def run(self,x:int,y:int)->int:
        return Interpreter(fuel=2000).run(self.program(x,y),{'x':x,'y':y})['acc']
    def describe(self)->str:
        return f'acc={self.initial}; repeat({self.iterations}): acc={"acc+" if self.update.startswith("add") else "acc-"}{self.update[-1]}'

@dataclass(frozen=True)
class LoopResult:
    candidate: LoopCandidate|None
    rounds: int
    counterexamples: tuple[tuple[int,int],...]
    verified_cases: int
    candidates_checked: int

def synthesize_loop(oracle: Callable[[int,int],int], domain=range(0,7), max_rounds=100)->LoopResult:
    points=list(product(domain,repeat=2))
    if not points or any(type(x) is not int or x<0 for pair in points for x in pair):
        raise ValueError('domain must be nonempty nonnegative integers')
    candidates=[LoopCandidate(a,u,n) for a,u,n in product((0,1,-1),('addx','addy','subx','suby'),('x','y','min','max'))]
    examples=[points[0]]
    checked=0
    for rnd in range(1,max_rounds+1):
        winner=None
        for c in candidates:
            checked+=1
            if all(c.run(x,y)==oracle(x,y) for x,y in examples):
                winner=c
                break
        if winner is None:
            return LoopResult(None,rnd,tuple(examples[1:]),len(points),checked)
        bad=next(((x,y) for x,y in points if winner.run(x,y)!=oracle(x,y)),None)
        if bad is None:
            return LoopResult(winner,rnd,tuple(examples[1:]),len(points),checked)
        if bad in examples:
            raise AssertionError('candidate violates training examples')
        examples.append(bad)
    return LoopResult(None,max_rounds,tuple(examples[1:]),len(points),checked)

if __name__=='__main__':
    r=synthesize_loop(lambda x,y:x*y)
    print(r)
