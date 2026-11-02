"""Three-register triangular recurrence synthesis with exact binomial-basis certificates.

Transition per iteration (simultaneous old-state semantics):
    acc <- acc + b
    b   <- b + a
    a   <- a + delta

The sequential interpreter executes the same transition in this order.
After n iterations:
    acc(n) = acc0 + b0*C(n,1) + a0*C(n,2) + delta*C(n,3).

This is an exact identity for nonnegative n with unbounded integers.
Finite oracle samples do NOT establish that an arbitrary oracle is cubic.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import comb
from control_flow import IntExpr, Statement, Interpreter

def _lit(n):return IntExpr('literal',atom=n)
def _reg(n):return IntExpr('register',atom=n)

@dataclass(frozen=True)
class CoupledProgram:
    acc0:int
    b0:int
    a0:int
    delta:int
    def __post_init__(self):
        if any(type(v) is not int for v in (self.acc0,self.b0,self.a0,self.delta)):
            raise TypeError('integer parameters required')
    def ast(self):
        change=_reg('a')
        for _ in range(abs(self.delta)):
            change=IntExpr('add' if self.delta>0 else 'sub',(change,_lit(1)))
        return (
            Statement('assign',name='acc',expr=_lit(self.acc0)),
            Statement('assign',name='b',expr=_lit(self.b0)),
            Statement('assign',name='a',expr=_lit(self.a0)),
            Statement('repeat',expr=_reg('n'),body=(
                Statement('assign',name='acc',expr=IntExpr('add',(_reg('acc'),_reg('b')))),
                Statement('assign',name='b',expr=IntExpr('add',(_reg('b'),_reg('a')))),
                Statement('assign',name='a',expr=change),
            )),
        )
    def run(self,n:int,fuel=100000):
        if type(n) is not int or n<0:raise ValueError('nonnegative integer n required')
        return Interpreter(fuel=fuel).run(self.ast(),{'n':n})['acc']
    def predict(self,n:int):
        if type(n) is not int or n<0:raise ValueError('nonnegative integer n required')
        return sum(c*comb(n,k) for k,c in enumerate(self.coefficients()))
    def coefficients(self):
        return (self.acc0,self.b0,self.a0,self.delta)

@dataclass(frozen=True)
class Result:
    program:CoupledProgram|None
    coefficients:tuple[int,int,int,int]|None
    verified_cases:int
    reason:str

def certify(program:CoupledProgram,expected:tuple[int,int,int,int]):
    if len(expected)!=4 or any(type(v) is not int for v in expected):
        raise ValueError('four integer binomial coefficients required')
    return program.coefficients()==expected

def synthesize(oracle,domain=range(9),*,max_coefficient=1000,fuel=100000):
    """Finite-difference inference, independently checked by the interpreter.

    The domain MUST contain 0,1,2,3 to identify the four coefficients.
    Returns no program if any supplied oracle observation contradicts the
    inferred cubic polynomial.
    """
    values=tuple(domain)
    if not values or any(type(n) is not int or n<0 for n in values):
        raise ValueError('nonempty nonnegative integer domain required')
    if not {0,1,2,3}.issubset(values):
        raise ValueError('domain must contain 0,1,2,3')
    if type(max_coefficient) is not int or max_coefficient<0 or fuel<1:
        raise ValueError('invalid budget')
    observations={n:oracle(n) for n in values}
    if any(type(v) is not int for v in observations.values()):
        raise TypeError('integer oracle required')
    a=[observations[n] for n in range(4)]
    coefficients=(a[0],a[1]-a[0],a[2]-2*a[1]+a[0],
                  a[3]-3*a[2]+3*a[1]-a[0])
    if any(abs(c)>max_coefficient for c in coefficients):
        return Result(None,None,len(observations),'coefficient budget exceeded')
    program=CoupledProgram(*coefficients)
    if any(program.predict(n)!=value for n,value in observations.items()):
        return Result(None,None,len(observations),'oracle contradicts cubic grammar')
    if any(program.run(n,fuel=fuel)!=value for n,value in observations.items()):
        return Result(None,None,len(observations),'interpreter mismatch')
    return Result(program,coefficients,len(observations),'finite observations matched')

if __name__=='__main__':
    for name,fn in [('cubic',lambda n:n**3),
                    ('tetrahedral',lambda n:comb(n,3)),
                    ('sum_squares',lambda n:n*(n-1)*(2*n-1)//6)]:
        result=synthesize(fn)
        print(name,result.coefficients,result.reason)
