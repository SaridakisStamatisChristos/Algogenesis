"""Exact symbolic certificates for the compositional loop grammar.

For nonnegative integer inputs, each repeat executes exactly count times.
The accumulator therefore computes a polynomial of degree at most two.
Coefficient equality proves equivalence for all nonnegative integer inputs
within this restricted grammar, independently of finite test coverage.
"""
from __future__ import annotations
from dataclasses import dataclass
from compositional import Program

MONOMIALS=('constant','x','y','x_squared','xy','y_squared')

@dataclass(frozen=True)
class Polynomial:
    coefficients: tuple[int,int,int,int,int,int]

    def evaluate(self,x:int,y:int)->int:
        c,a,b,xx,xy,yy=self.coefficients
        return c+a*x+b*y+xx*x*x+xy*x*y+yy*y*y

    def __str__(self):
        return ' + '.join(f'{v}*{name}' for v,name in zip(self.coefficients,MONOMIALS) if v) or '0'

def derive(program:Program)->Polynomial:
    c=[program.initial,0,0,0,0,0]
    terms={('x','one'):1,('y','one'):2,('x','x'):3,
           ('x','y'):4,('y','x'):4,('y','y'):5}
    for stage in program.stages:
        if stage.count not in ('x','y') or stage.source not in ('x','y','one') or stage.operation not in ('add','sub'):
            raise ValueError('program outside supported certificate grammar')
        c[terms[(stage.count,stage.source)]]+=1 if stage.operation=='add' else -1
    return Polynomial(tuple(c))

def equivalent(left:Program,right:Polynomial)->bool:
    """Exact for all nonnegative x,y within this loop grammar."""
    return derive(left)==right

def certificate(program:Program,expected:Polynomial)->dict:
    actual=derive(program)
    return {'method':'symbolic-polynomial-normalization',
            'domain':'all nonnegative integers x,y',
            'actual':dict(zip(MONOMIALS,actual.coefficients)),
            'expected':dict(zip(MONOMIALS,expected.coefficients)),
            'equivalent':actual==expected,
            'assumptions':['count is nonnegative','x and y are immutable',
                           'accumulator is unbounded integer','loop body has no branching']}

if __name__=='__main__':
    from compositional import synthesize
    r=synthesize(lambda x,y:x*x+y*y)
    print(certificate(r.program,Polynomial((0,0,0,1,0,1))))
