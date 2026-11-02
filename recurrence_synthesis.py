"""Synthesis of loop-carried affine recurrences with exact polynomial certificates.

Grammar:
    acc = a0; state = s0
    repeat(x):
        acc = acc + sign * state
        state = state + delta

The loop carries mutable state. Its result is
a0 + sign*(x*s0 + delta*x*(x-1)//2).
This identity is exact over nonnegative integer x, with unbounded integers.
"""
from __future__ import annotations
from dataclasses import dataclass
from control_flow import IntExpr, Statement, Interpreter

@dataclass(frozen=True)
class Recurrence:
    initial_acc:int
    initial_state:int
    delta:int
    sign:int=1
    def __post_init__(self):
        if any(type(v) is not int for v in (self.initial_acc,self.initial_state,self.delta,self.sign)):
            raise TypeError('integer coefficients required')
        if self.sign not in (-1,1):
            raise ValueError('sign must be +1 or -1')
    def ast(self):
        def lit(n):return IntExpr('literal',atom=n)
        def reg(n):return IntExpr('register',atom=n)
        def add_constant(name,value):
            expr=reg(name)
            for _ in range(abs(value)):
                expr=IntExpr('add' if value>0 else 'sub',(expr,lit(1)))
            return Statement('assign',name=name,expr=expr)
        return (
            Statement('assign',name='acc',expr=lit(self.initial_acc)),
            Statement('assign',name='state',expr=lit(self.initial_state)),
            Statement('repeat',expr=reg('x'),body=(
                Statement('assign',name='acc',expr=IntExpr('add' if self.sign>0 else 'sub',(reg('acc'),reg('state')))),
                add_constant('state',self.delta),
            )),
        )
    def run(self,x:int,fuel=100000):
        if type(x) is not int or x<0:raise ValueError('x must be a nonnegative integer')
        return Interpreter(fuel=fuel).run(self.ast(),{'x':x})['acc']
    def predict(self,x:int):
        if type(x) is not int or x<0:raise ValueError('x must be a nonnegative integer')
        return self.initial_acc+self.sign*(x*self.initial_state+self.delta*x*(x-1)//2)
    def certificate(self):
        """Return coefficients for (1, x, binomial(x,2))."""
        return (self.initial_acc,self.sign*self.initial_state,self.sign*self.delta)

@dataclass(frozen=True)
class Result:
    program:Recurrence|None
    checked:int
    verified_cases:int
    certificate:tuple[int,int,int]|None
    exhausted:bool

def certify(program:Recurrence,coefficients:tuple[int,int,int]):
    """Exact identity for every nonnegative integer x in the stated grammar."""
    if len(coefficients)!=3 or any(type(v) is not int for v in coefficients):
        raise ValueError('expected three integer coefficients')
    return program.certificate()==coefficients

def synthesize(oracle,domain=range(9),*,coefficient_bound=3,max_candidates=10000,fuel=100000):
    values=tuple(domain)
    if not values or any(type(x) is not int or x<0 for x in values):
        raise ValueError('nonempty nonnegative integer domain required')
    if not 0<=coefficient_bound<=12 or max_candidates<1 or fuel<1:
        raise ValueError('invalid resource budget')
    expected={x:oracle(x) for x in values}
    if any(type(y) is not int for y in expected.values()):
        raise TypeError('integer oracle required')
    checked=0
    for a in range(-coefficient_bound,coefficient_bound+1):
        for s in range(-coefficient_bound,coefficient_bound+1):
            for delta in range(-coefficient_bound,coefficient_bound+1):
                for sign in (1,-1):
                    checked+=1
                    if checked>max_candidates:
                        return Result(None,checked,len(expected),None,True)
                    p=Recurrence(a,s,delta,sign)
                    if all(p.predict(x)==y for x,y in expected.items()):
                        if all(p.run(x,fuel)==y for x,y in expected.items()):
                            return Result(p,checked,len(expected),p.certificate(),False)
    return Result(None,checked,len(expected),None,False)

if __name__=='__main__':
    for name,oracle in [('triangular',lambda n:n*(n-1)//2),
                        ('sum_1_to_n',lambda n:n*(n+1)//2),
                        ('quadratic',lambda n:n*n)]:
        r=synthesize(oracle)
        print(name,r)
