"""Exact fixed-share expert tracking and quantization-aware regret certificates.

Classical Herbster-Warmuth Fixed Share. Not a new SOTA algorithm.
All observations must lie inside a declared rational interval.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt
from regret_forecast import BoundedExperts,_exact

@dataclass(frozen=True)
class SwitchingCertificate:
    rounds:int
    switches:int
    comparator_loss:Fraction
    learner_loss:Fraction
    regret:Fraction
    bound:Fraction
    valid:bool

def _ceil_log2_ratio(numerator,denominator):
    if numerator<0 or denominator<=0:raise ValueError("positive ratio required")
    if numerator<=denominator:return 0
    guess=max(0,numerator.bit_length()-denominator.bit_length())
    if (denominator<<guess)<numerator:guess+=1
    return guess

class FixedShareExperts(BoundedExperts):
    """Online fixed-share machine with exact rational state and discrete grids."""
    def __init__(self,experts,*,lower,upper,share=Fraction(1,8),
                 eta=Fraction(1,8),resolution=512,prediction_resolution=1<<256):
        alpha=_exact(share)
        if not 0<alpha<1:raise ValueError("share must be in (0,1)")
        super().__init__(experts,lower=lower,upper=upper,eta=eta,
                         resolution=resolution,prediction_resolution=prediction_resolution)
        self.share=alpha

    def observe(self,actual):
        record=super().observe(actual)
        total=sum(self.weights.values(),Fraction(0))
        shared=self.share*total/len(self.names)
        for name in self.names:
            self.weights[name]=(1-self.share)*self.weights[name]+shared
        return record

    def certificate(self):
        raise NotImplementedError("use switching_certificate for fixed-share")

    def switching_certificate(self,path):
        if self._pending is not None:raise RuntimeError("finish pending forecast first")
        chosen=tuple(path)
        if len(chosen)!=len(self.records):raise ValueError("path length mismatch")
        if any(name not in self.names for name in chosen):raise ValueError("unknown expert")
        t=len(chosen)
        if not t:return SwitchingCertificate(0,0,Fraction(0),Fraction(0),Fraction(0),Fraction(0),True)
        switches=sum(chosen[i]!=chosen[i-1] for i in range(1,t))
        comparator=sum((dict(r.expert_losses)[name] for r,name in zip(self.records,chosen)),Fraction(0))
        learner=sum((r.learner_loss for r in self.records),Fraction(0))
        k=len(self.names)
        switch_bits=_ceil_log2_ratio(k*self.share.denominator,self.share.numerator)
        penalty=(Fraction((k-1).bit_length())
                 +(t-1-switches)*self.share/(1-self.share)+switches*switch_bits)
        bound=(penalty/self.eta+self.eta*t
               +Fraction(t,self.resolution)+Fraction(t,2*self.prediction_resolution))
        regret=learner-comparator
        return SwitchingCertificate(t,switches,comparator,learner,regret,bound,regret<=bound)

    def best_switching_path(self,max_switches):
        """Post-hoc exact DP oracle, O(T*K**2*S) time and O(T*K*S) memory."""
        if self._pending is not None:raise RuntimeError("finish pending forecast")
        if type(max_switches) is not int or max_switches<0:
            raise ValueError("nonnegative integer switch budget required")
        t=len(self.records)
        if not t:return ()
        budget=min(max_switches,t-1)
        first=dict(self.records[0].expert_losses)
        costs={(0,name):first[name] for name in self.names}
        parents=[]
        for record in self.records[1:]:
            local=dict(record.expert_losses)
            next_costs={};predecessors={}
            for key,old_cost in sorted(costs.items()):
                used,previous=key
                for name in self.names:
                    updated=used+int(name!=previous)
                    if updated>budget:continue
                    candidate_key=(updated,name)
                    candidate_cost=old_cost+local[name]
                    if candidate_key not in next_costs or candidate_cost<next_costs[candidate_key]:
                        next_costs[candidate_key]=candidate_cost
                        predecessors[candidate_key]=key
            costs=next_costs;parents.append(predecessors)
        current=min(costs,key=lambda key:(costs[key],key))
        path=[current[1]]
        for predecessor in reversed(parents):
            current=predecessor[current];path.append(current[1])
        return tuple(reversed(path))

def tuned_tracking_parameters(horizon,expert_count,switch_budget):
    """Horizon-and-budget tuning; no observed labels or future values."""
    if any(type(v) is not int for v in (horizon,expert_count,switch_budget)):
        raise TypeError("integer parameters required")
    if horizon<1 or expert_count<1 or not 0<=switch_budget<horizon:
        raise ValueError("invalid parameters")
    alpha=Fraction(max(1,switch_budget),horizon+1)
    switch_bits=_ceil_log2_ratio(expert_count*alpha.denominator,alpha.numerator)
    penalty=(Fraction((expert_count-1).bit_length())
             +(horizon-1-switch_budget)*alpha/(1-alpha)+switch_budget*switch_bits)
    if penalty==0:return Fraction(1,2),alpha
    estimate=(horizon*penalty.denominator)//penalty.numerator
    q=max(2,isqrt(max(1,estimate)))
    while q*q*penalty<horizon:q+=1
    return Fraction(1,q),alpha
