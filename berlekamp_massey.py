"""Exact Berlekamp-Massey recurrence inference over rational numbers.

Minimum linear complexity on a finite trace is not proof of future behavior.
"""
from dataclasses import dataclass
from fractions import Fraction

@dataclass(frozen=True)
class BMResult:
    coefficients:tuple[Fraction,...]
    complexity:int
    observations:int
    def predict_next(self,history):
        if len(history)<self.complexity:raise ValueError("insufficient history")
        if not self.complexity:return Fraction(0)
        return sum(c*history[-self.complexity+j] for j,c in enumerate(self.coefficients))

def infer(observations):
    seq=tuple(observations)
    if not seq:raise ValueError("nonempty observations required")
    if any(type(x) not in (int,Fraction) for x in seq):
        raise TypeError("only exact int/Fraction observations accepted")
    seq=tuple(Fraction(x) for x in seq)
    c=[Fraction(1)];b=[Fraction(1)]
    L=0;m=1;last=Fraction(1)
    for n,value in enumerate(seq):
        discrepancy=value+sum(c[i]*seq[n-i] for i in range(1,L+1))
        if discrepancy==0:
            m+=1
            continue
        old=c[:]
        needed=len(b)+m
        if len(c)<needed:c.extend([Fraction(0)]*(needed-len(c)))
        factor=discrepancy/last
        for i,v in enumerate(b):c[i+m]-=factor*v
        if 2*L<=n:
            L=n+1-L;b=old;last=discrepancy;m=1
        else:m+=1
    result=BMResult(tuple(-c[i] for i in range(L,0,-1)),L,len(seq))
    if any(result.predict_next(seq[:n])!=seq[n] for n in range(L,len(seq))):
        raise AssertionError("recurrence does not reproduce observations")
    return result
