"""Scalar-output recurrence inference via exact Hankel linear algebra.

Given y[0],...,y[N-1], find the smallest order k<=max_order with
y[n+k] = sum(c[j]*y[n+j] for j in range(k)).
A unique rational solution and exact validation are required.
Finite observations never prove that the unknown source follows the
recurrence forever; a returned model is a hypothesis.
"""
from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class LinearRecurrence:
    coefficients: tuple[Fraction,...]
    initial: tuple[Fraction,...]
    def __post_init__(self):
        k=len(self.coefficients)
        if not k or len(self.initial)!=k:raise ValueError("order/initial mismatch")
        if any(not isinstance(v,(int,Fraction)) or isinstance(v,bool) for v in self.coefficients+self.initial):
            raise TypeError("exact rational values required")
    def generate(self,count):
        if type(count) is not int or count<0:raise ValueError("invalid count")
        seq=list(self.initial)
        while len(seq)<count:
            seq.append(sum(c*seq[-len(self.coefficients)+j] for j,c in enumerate(self.coefficients)))
        return tuple(seq[:count])
    def next(self,window):
        if len(window)!=len(self.coefficients):raise ValueError("window length mismatch")
        return sum(c*v for c,v in zip(self.coefficients,window))

@dataclass(frozen=True)
class Discovery:
    model:LinearRecurrence|None
    order:int|None
    reason:str

def _solve(rows,values):
    if not rows:return None,"underdetermined"
    width=len(rows[0]); a=[[Fraction(v) for v in row]+[Fraction(t)] for row,t in zip(rows,values)]
    rank=0
    for col in range(width):
        pivot=next((r for r in range(rank,len(a)) if a[r][col]),None)
        if pivot is None:continue
        a[rank],a[pivot]=a[pivot],a[rank]
        p=a[rank][col];a[rank]=[v/p for v in a[rank]]
        for r in range(len(a)):
            if r!=rank:
                factor=a[r][col]
                if factor:a[r]=[v-factor*w for v,w in zip(a[r],a[rank])]
        rank+=1
    if any(all(v==0 for v in row[:width]) and row[-1]!=0 for row in a):
        return None,"inconsistent"
    if rank<width:return None,"underdetermined"
    return tuple(a[i][-1] for i in range(width)),"unique"

def synthesize(observations,max_order=None):
    values=tuple(observations)
    if len(values)<3:raise ValueError("at least three observations required")
    if any(type(v) is not int and type(v) is not Fraction for v in values):
        raise TypeError("exact rational observations required")
    if max_order is None:max_order=(len(values)-1)//2
    if type(max_order) is not int or max_order<1:raise ValueError("invalid maximum order")
    # At least k independent equations plus one held-out transition.
    limit=min(max_order,(len(values)-1)//2)
    for k in range(1,limit+1):
        rows=[values[i:i+k] for i in range(len(values)-k)]
        targets=values[k:]
        coefficients,status=_solve(rows,targets)
        if coefficients is None:continue
        model=LinearRecurrence(coefficients,values[:k])
        if model.generate(len(values))==values:
            return Discovery(model,k,"exact fit on observed trace")
    return Discovery(None,None,"no uniquely identifiable recurrence within order budget")

def certify(left,right):
    """Exact equality of recurrence definitions, not of arbitrary black boxes."""
    return left==right
