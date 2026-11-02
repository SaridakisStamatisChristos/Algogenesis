"""Causal stability-gated expert selection for exact sequences and noisy streams.

A model's historical exactness is evidence about past points, not a proof
of future validity. The selector has no distribution-free prediction bound.
"""
from dataclasses import dataclass
from fractions import Fraction
from regret_forecast import EXPERTS, causal_candidates, _exact


@dataclass(frozen=True)
class Decision:
    index: int
    selected: str
    predicted: Fraction
    actual: Fraction
    candidates: tuple[tuple[str, Fraction], ...]
    scores: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class Evaluation:
    records: tuple[Decision, ...]
    selected_mae: Fraction
    candidate_mae: tuple[tuple[str, Fraction], ...]
    switches: int


def evaluate(observations, *, warmup=32, season=11, calibration=12,
             lookback=12, stability=5, max_weight=Fraction(1,4)):
    xs = tuple(_exact(x) for x in observations)
    if any(type(v) is not int for v in (warmup, season, calibration, lookback, stability)):
        raise TypeError('integer parameters required')
    if (warmup < 32 or len(xs) <= warmup or calibration < 5
            or warmup-calibration < max(season,20,3) or lookback < 1
            or stability < 1 or stability > calibration or not 1 <= season <= warmup):
        raise ValueError('invalid calibration, window or history')
    alpha = _exact(max_weight)
    if alpha < 0 or alpha > 2:
        raise ValueError('max_weight must be in [0,2]')
    errors={name:[] for name in EXPERTS}
    records=[]
    for t in range(warmup-calibration,len(xs)):
        candidates=causal_candidates(xs[:t],season=season)
        if t>=warmup:
            scores={name: (sum(errors[name][-lookback:],Fraction(0)) /
                          len(errors[name][-lookback:])
                          + alpha*max(errors[name][-lookback:]))
                    for name in EXPERTS}
            # A recurrence is eligible only if its recent forecasts were
            # exactly correct. This is finite evidence, not certification.
            eligible=[name for name in EXPERTS if not name.startswith('bm_')]
            for name in ('bm_short','bm_long'):
                if len(errors[name])>=stability and all(e==0 for e in errors[name][-stability:]):
                    eligible.append(name)
            selected=min(eligible,key=lambda name:(scores[name],EXPERTS.index(name)))
            records.append(Decision(t,selected,candidates[selected],xs[t],
                                    tuple(candidates.items()),tuple(scores.items())))
        actual=xs[t]
        denominator=1+abs(actual)
        for name,value in candidates.items():
            errors[name].append(abs(value-actual)/denominator)
    count=len(records)
    return Evaluation(tuple(records),
        sum((abs(r.predicted-r.actual) for r in records),Fraction(0))/count,
        tuple((name,sum((abs(dict(r.candidates)[name]-r.actual) for r in records),Fraction(0))/count)
              for name in EXPERTS),
        sum(a.selected!=b.selected for a,b in zip(records,records[1:])))
