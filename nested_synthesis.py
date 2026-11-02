"""Nested-loop CEGIS with exact polynomial certificates (degree <= 3).

Bounds are immutable nonnegative x/y. Each loop body adds/subtracts x/y/1
to an unbounded integer accumulator. No general-purpose synthesis claim.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from control_flow import IntExpr, Statement, Interpreter

BASIS=((0,0),(1,0),(0,1),(2,0),(1,1),(0,2),(3,0),(2,1),(1,2),(0,3))
INDEX={term:i for i,term in enumerate(BASIS)}

@dataclass(frozen=True,order=True)
class Term:
    loops:tuple[str,...]
    operand:str
    sign:int=1
    def __post_init__(self):
        if not 1<=len(self.loops)<=2 or any(v not in ('x','y') for v in self.loops):
            raise ValueError('one or two loops over x/y required')
        if self.operand not in ('x','y','one') or self.sign not in (-1,1):
            raise ValueError('invalid update')
    def monomial(self):
        return self.loops.count('x')+(self.operand=='x'),self.loops.count('y')+(self.operand=='y')
    def statement(self):
        acc=IntExpr('register',atom='acc')
        value=IntExpr('literal',atom=1) if self.operand=='one' else IntExpr('register',atom=self.operand)
        body=(Statement('assign',name='acc',expr=IntExpr('add' if self.sign==1 else 'sub',(acc,value))),)
        for var in reversed(self.loops):
            body=(Statement('repeat',expr=IntExpr('register',atom=var),body=body),)
        return body[0]

@dataclass(frozen=True)
class NestedProgram:
    initial:int
    terms:tuple[Term,...]
    def ast(self):
        return (Statement('assign',name='acc',expr=IntExpr('literal',atom=self.initial)),)+tuple(t.statement() for t in self.terms)
    def run(self,x:int,y:int,fuel:int=100000):
        return Interpreter(fuel=fuel).run(self.ast(),{'x':x,'y':y})['acc']
    def polynomial(self):
        coeff=[0]*len(BASIS)
        coeff[0]=self.initial
        for term in self.terms:
            coeff[INDEX[term.monomial()]]+=term.sign
        return tuple(coeff)
    def describe(self):
        return 'acc = '+str(self.initial)+'\n'+'\n'.join(' '.join('repeat('+v+'):' for v in t.loops)+' acc = acc '+('+' if t.sign==1 else '-')+' '+t.operand for t in self.terms)

@dataclass(frozen=True)
class Result:
    program:NestedProgram|None
    rounds:int
    candidates:int
    verified_cases:int
    counterexamples:tuple[tuple[int,int],...]
    exhausted:bool
    polynomial:tuple[int,...]|None

def _terms(max_depth):
    unique={}
    for depth in range(1,max_depth+1):
        for loops in product(('x','y'),repeat=depth):
            for operand in ('one','x','y'):
                for sign in (1,-1):
                    term=Term(loops,operand,sign)
                    unique.setdefault((term.monomial(),sign),term)
    return tuple(sorted(unique.values()))

def _enumerate(examples,max_terms,max_depth):
    terms=_terms(max_depth)
    effects={t:tuple(t.sign*x**t.monomial()[0]*y**t.monomial()[1] for x,y in examples) for t in terms}
    frontier={(0,)*len(examples):()}
    seen=set(frontier)
    for initial in (0,1,-1):
        yield NestedProgram(initial,())
    for _ in range(max_terms):
        nxt={}
        for sig,seq in frontier.items():
            for term in terms:
                if seq and term<seq[-1]:
                    continue
                output=tuple(a+b for a,b in zip(sig,effects[term]))
                if output in seen or output in nxt:
                    continue
                nxt[output]=seq+(term,)
        for seq in nxt.values():
            for initial in (0,1,-1):
                yield NestedProgram(initial,seq)
        seen.update(nxt)
        frontier=nxt

def synthesize(oracle,domain=range(4),*,max_terms=2,max_depth=2,max_rounds=25,max_candidates=100000,fuel=100000):
    values=tuple(domain)
    if not values or any(type(v) is not int or v<0 for v in values):
        raise ValueError('nonempty nonnegative integer domain required')
    if not 0<=max_terms<=4 or not 1<=max_depth<=2 or min(max_rounds,max_candidates,fuel)<1:
        raise ValueError('invalid search budget')
    points=tuple(product(values,repeat=2))
    expected={p:oracle(*p) for p in points}
    if any(type(v) is not int for v in expected.values()):
        raise TypeError('integer oracle required')
    examples=[points[0]]
    checked=0
    for rnd in range(1,max_rounds+1):
        winner=None
        for candidate in _enumerate(tuple(examples),max_terms,max_depth):
            checked+=1
            if checked>max_candidates:
                return Result(None,rnd,checked,len(points),tuple(examples[1:]),True,None)
            poly=candidate.polynomial()
            if all(sum(coef*x**a*y**b for coef,(a,b) in zip(poly,BASIS))==expected[x,y] for x,y in examples):
                winner=candidate
                break
        if winner is None:
            return Result(None,rnd,checked,len(points),tuple(examples[1:]),False,None)
        mismatch=None
        for x,y in points:
            try:
                actual=winner.run(x,y,fuel)
            except (ValueError,RuntimeError):
                actual=None
            if actual!=expected[x,y]:
                mismatch=(x,y)
                break
        if mismatch is None:
            return Result(winner,rnd,checked,len(points),tuple(examples[1:]),False,winner.polynomial())
        if mismatch in examples:
            raise AssertionError('candidate contradicts training example')
        examples.append(mismatch)
    return Result(None,max_rounds,checked,len(points),tuple(examples[1:]),True,None)

def certify(program:NestedProgram,expected:tuple[int,...]):
    if len(expected)!=len(BASIS) or any(type(v) is not int for v in expected):
        raise ValueError('invalid polynomial vector')
    return program.polynomial()==expected

if __name__=='__main__':
    for name,oracle in [('x3',lambda x,y:x**3),('x2y',lambda x,y:x*x*y),('x3+y3',lambda x,y:x**3+y**3)]:
        result=synthesize(oracle)
        print(name,result.rounds,result.candidates,result.program.describe() if result.program else None)
