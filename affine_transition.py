"""Infer integer affine state transitions from traces using exact rational elimination.

For state s in Z^d, model s_next = A*s + b. A unique integer
solution requires full column rank of augmented observations (s,1).
Matching a finite trace is not a proof about an arbitrary black-box oracle.
"""
from dataclasses import dataclass
from fractions import Fraction

def _vector(v,d=None):
    v=tuple(v)
    if not v or (d is not None and len(v)!=d) or any(type(x) is not int for x in v):
        raise ValueError('expected nonempty integer vector of fixed dimension')
    return v

@dataclass(frozen=True)
class AffineTransition:
    matrix:tuple[tuple[int,...],...]
    bias:tuple[int,...]
    def __post_init__(self):
        d=len(self.bias)
        _vector(self.bias)
        if len(self.matrix)!=d:raise ValueError('matrix must be square')
        for row in self.matrix:_vector(row,d)
    def step(self,state):
        state=_vector(state,len(self.bias))
        return tuple(sum(a*s for a,s in zip(row,state))+b for row,b in zip(self.matrix,self.bias))
    def iterate(self,state,n):
        if type(n) is not int or n<0:raise ValueError('invalid iteration count')
        state=_vector(state,len(self.bias))
        for _ in range(n):state=self.step(state)
        return state
    def power(self,state,n):
        """Independent logarithmic-time augmented matrix exponentiation."""
        if type(n) is not int or n<0:raise ValueError('invalid iteration count')
        state=_vector(state,len(self.bias))
        d=len(state)
        base=tuple(tuple(self.matrix[i])+(self.bias[i],) for i in range(d))+((0,)*d+(1,),)
        size=d+1
        result=tuple(tuple(int(i==j) for j in range(size)) for i in range(size))
        def mul(a,b):
            return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(size)) for j in range(size)) for i in range(size))
        while n:
            if n&1:result=mul(result,base)
            base=mul(base,base)
            n//=2
        v=state+(1,)
        return tuple(sum(result[i][j]*v[j] for j in range(size)) for i in range(d))

@dataclass(frozen=True)
class Discovery:
    transition:AffineTransition|None
    rank:int
    observations:int
    reason:str

def _solve(rows,outputs):
    m=len(rows)
    width=len(rows[0])
    a=[[Fraction(x) for x in row]+[Fraction(y)] for row,y in zip(rows,outputs)]
    pivots=[]
    for col in range(width):
        pivot=next((r for r in range(len(pivots),m) if a[r][col]),None)
        if pivot is None:continue
        k=len(pivots)
        a[k],a[pivot]=a[pivot],a[k]
        scale=a[k][col]
        a[k]=[x/scale for x in a[k]]
        for r in range(m):
            if r!=k:
                factor=a[r][col]
                if factor:a[r]=[x-factor*y for x,y in zip(a[r],a[k])]
        pivots.append(col)
    if any(all(not x for x in row[:width]) and row[-1] for row in a):
        return None,len(pivots),'inconsistent trace'
    if len(pivots)<width:return None,len(pivots),'underdetermined transition'
    out=[Fraction(0)]*width
    for i,col in enumerate(pivots):out[col]=a[i][-1]
    if any(v.denominator!=1 for v in out):return None,len(pivots),'nonintegral transition'
    return tuple(map(int,out)),len(pivots),'unique integer transition'

def synthesize(trace):
    states=tuple(_vector(s) for s in trace)
    if len(states)<2:raise ValueError('at least two states required')
    d=len(states[0])
    if any(len(s)!=d for s in states):raise ValueError('inconsistent state dimensions')
    rows=tuple(s+(1,) for s in states[:-1])
    coefficients=[]
    rank=0
    for j in range(d):
        coeff,rank,reason=_solve(rows,tuple(s[j] for s in states[1:]))
        if coeff is None:return Discovery(None,rank,len(states),reason)
        coefficients.append(coeff)
    model=AffineTransition(tuple(c[:-1] for c in coefficients),tuple(c[-1] for c in coefficients))
    if any(model.step(s)!=nxt for s,nxt in zip(states,states[1:])):
        raise AssertionError('solver and evaluator disagree')
    return Discovery(model,rank,len(states),'unique integer transition')

def certify(left,right):
    """Exact transition equality for all initial integer states and n>=0."""
    return left==right
