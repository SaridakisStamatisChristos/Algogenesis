"""CEGIS for conditional integer programs with affine leaves and comparison guards.

Search uses semantic partitions; independent verification executes generated ASTs
with control_flow.Interpreter. Correctness is finite-domain only.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from control_flow import IntExpr, Predicate, Statement, Interpreter

@dataclass(frozen=True,order=True)
class Affine:
    a:int
    b:int
    c:int
    def value(self,x,y): return self.a*x+self.b*y+self.c
    def expr(self):
        def lit(n):return IntExpr('literal',atom=n)
        def reg(n):return IntExpr('register',atom=n)
        def mul(n,var):
            if n==0:return lit(0)
            out=lit(0)
            for _ in range(abs(n)):
                out=IntExpr('add' if n>0 else 'sub',(out,reg(var)))
            return out
        return IntExpr('add',(IntExpr('add',(mul(self.a,'x'),mul(self.b,'y'))),lit(self.c)))

@dataclass(frozen=True,order=True)
class Guard:
    lhs:str
    op:str
    rhs:str
    def value(self,x,y):
        d={'x':x,'y':y,'zero':0}
        a,b=d[self.lhs],d[self.rhs]
        return {'lt':a<b,'le':a<=b,'eq':a==b}[self.op]
    def predicate(self):
        def expr(name):return IntExpr('literal',atom=0) if name=='zero' else IntExpr('register',atom=name)
        return Predicate(self.op,expr(self.lhs),expr(self.rhs))

@dataclass(frozen=True)
class Node:
    leaf:Affine|None=None
    guard:Guard|None=None
    yes:'Node|None'=None
    no:'Node|None'=None
    def __post_init__(self):
        if (self.leaf is None)==(self.guard is None):raise ValueError('exactly one node kind required')
        if self.guard is not None and (self.yes is None or self.no is None):raise ValueError('missing branch')
    def evaluate(self,x,y):
        if self.leaf is not None:return self.leaf.value(x,y)
        return (self.yes if self.guard.value(x,y) else self.no).evaluate(x,y)
    def statement(self):
        if self.leaf is not None:return Statement('assign',name='out',expr=self.leaf.expr())
        return Statement('if',condition=self.guard.predicate(),body=(self.yes.statement(),),otherwise=(self.no.statement(),))
    def run(self,x,y,fuel=10000):
        return Interpreter(fuel=fuel).run((self.statement(),),{'x':x,'y':y})['out']
    def describe(self):
        if self.leaf is not None:return f'{self.leaf.a}*x + {self.leaf.b}*y + {self.leaf.c}'
        return f'if {self.guard.lhs} {self.guard.op} {self.guard.rhs}: ({self.yes.describe()}) else: ({self.no.describe()})'

@dataclass(frozen=True)
class Result:
    program:Node|None
    rounds:int
    verified_cases:int
    counterexamples:tuple[tuple[int,int],...]
    exhausted:bool
    partitions:int

GUARDS=tuple(Guard(a,op,b) for a,b in (('x','y'),('y','x'),('x','zero'),('y','zero'),('zero','x'),('zero','y')) for op in ('lt','le','eq'))

def _learn(examples,leaves,depth,budget):
    visited=0
    @lru_cache(None)
    def solve(indices,remaining):
        nonlocal visited
        visited+=1
        if visited>budget:raise RuntimeError('partition budget exhausted')
        for leaf in leaves:
            if all(leaf.value(*examples[i][0])==examples[i][1] for i in indices):
                return Node(leaf=leaf)
        if remaining==0:return None
        for guard in GUARDS:
            yes=tuple(i for i in indices if guard.value(*examples[i][0]))
            if not yes or len(yes)==len(indices):continue
            no=tuple(i for i in indices if i not in yes)
            a=solve(yes,remaining-1)
            if a is None:continue
            b=solve(no,remaining-1)
            if b is not None:return Node(guard=guard,yes=a,no=b)
        return None
    try:return solve(tuple(range(len(examples))),depth),visited,False
    except RuntimeError:return None,visited,True

def synthesize(oracle,domain=range(-3,4),*,max_depth=2,max_rounds=40,max_partitions=100000,coefficient_bound=1,constant_bound=1,fuel=10000):
    values=tuple(domain)
    if not values or any(type(v) is not int for v in values):raise ValueError('integer domain required')
    if not 0<=max_depth<=4 or min(max_rounds,max_partitions,fuel)<1 or not 0<=coefficient_bound<=3 or not 0<=constant_bound<=5:
        raise ValueError('invalid resource budget')
    points=tuple(product(values,repeat=2))
    expected={p:oracle(*p) for p in points}
    if any(type(v) is not int for v in expected.values()):raise TypeError('integer oracle required')
    leaves=tuple(sorted((Affine(a,b,c) for a,b,c in product(range(-coefficient_bound,coefficient_bound+1),range(-coefficient_bound,coefficient_bound+1),range(-constant_bound,constant_bound+1))),key=lambda e:(abs(e.a)+abs(e.b)+abs(e.c),abs(e.c),e)))
    examples=[points[0]]
    total=0
    for rnd in range(1,max_rounds+1):
        candidate,visited,exhausted=_learn(tuple((p,expected[p]) for p in examples),leaves,max_depth,max_partitions-total)
        total+=visited
        if exhausted:return Result(None,rnd,len(points),tuple(examples[1:]),True,total)
        if candidate is None:return Result(None,rnd,len(points),tuple(examples[1:]),False,total)
        bad=next((p for p in points if candidate.run(*p,fuel=fuel)!=expected[p]),None)
        if bad is None:return Result(candidate,rnd,len(points),tuple(examples[1:]),False,total)
        if bad in examples:raise AssertionError('counterexample was already learned')
        examples.append(bad)
    return Result(None,max_rounds,len(points),tuple(examples[1:]),True,total)

if __name__=='__main__':
    for name,fn in [('max',max),('absdiff',lambda x,y:abs(x-y)),('clamp',lambda x,y:max(0,min(x,y)))]:
        r=synthesize(fn)
        print(name,r.rounds,r.partitions,r.program.describe() if r.program else None)
