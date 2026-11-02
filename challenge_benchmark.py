"""Seeded external-to-training challenge families for recurrence inference.

Evaluates exact, perturbed and regime-switching sequences against both
methods on identical prefixes. Reports coverage and held-out error,
not a claim of state-of-the-art general algorithm synthesis.
"""
from fractions import Fraction
from random import Random
from statistics import median
from time import perf_counter_ns
from observable_recurrence import synthesize
from berlekamp_massey import infer

def challenges(seed=20261102):
    rng=Random(seed)
    cases={}
    for j in range(6):
        a=rng.randint(1,4); b=rng.randint(-3,3)
        cases[f"affine_{j}"]=tuple(a*n+b for n in range(64))
    for j in range(6):
        a=rng.randint(1,3); b=rng.randint(-2,2)
        cases[f"quadratic_{j}"]=tuple(a*n*n+b*n+1 for n in range(64))
    for j in range(6):
        base=rng.randint(2,4)
        cases[f"exponential_{j}"]=tuple(base**n for n in range(64))
    for j in range(6):
        phase=rng.randint(0,6)
        cases[f"periodic_{j}"]=tuple(((n+phase)%7)-3 for n in range(64))
    for j in range(6):
        offset=rng.randint(0,3)
        cases[f"perturbed_{j}"]=tuple(2**n+(1 if n%11==offset else 0) for n in range(64))
    for j in range(6):
        switch=34+j
        cases[f"regime_{j}"]=tuple(2**n if n<switch else 3**n for n in range(64))
    return cases

def _forecast(prefix,steps,method):
    if method=="hankel":
        result=synthesize(prefix)
        if result.model is None:return None
        return result.model.generate(len(prefix)+steps)[-steps:]
    result=infer(prefix)
    if result.complexity==0:return (Fraction(0),)*steps
    history=list(prefix)
    for _ in range(steps):history.append(result.predict_next(history))
    return tuple(history[-steps:])

def evaluate(*,seed=20261102,train=32,horizon=8,repeats=3):
    if any(type(x) is not int for x in (seed,train,horizon,repeats)):
        raise TypeError("integer parameters required")
    if train<3 or horizon<1 or repeats<1 or train+horizon>64:
        raise ValueError("invalid evaluation window")
    rows=[]
    for name,series in challenges(seed).items():
        prefix=series[:train];actual=series[train:train+horizon]
        for method in ("hankel","berlekamp_massey","persistence","linear"):
            def run():
                if method=="persistence":return (prefix[-1],)*horizon
                if method=="linear":
                    delta=prefix[-1]-prefix[-2]
                    return tuple(prefix[-1]+delta*(j+1) for j in range(horizon))
                return _forecast(prefix,horizon,method)
            timings=[];predicted=None
            for _ in range(repeats):
                start=perf_counter_ns();predicted=run();timings.append(perf_counter_ns()-start)
            error=None if predicted is None else sum((abs(Fraction(a)-Fraction(b)) for a,b in zip(actual,predicted)),Fraction(0))/horizon
            rows.append({"case":name,"family":name.rsplit("_",1)[0],
                         "method":method,"covered":predicted is not None,
                         "exact":predicted is not None and tuple(predicted)==actual,
                         "mae":None if error is None else str(error),
                         "median_ns":int(median(timings))})
    return tuple(rows)

def summarize(rows):
    out={}
    for method in ("hankel","berlekamp_massey","persistence","linear"):
        subset=[r for r in rows if r["method"]==method]
        covered=[r for r in subset if r["covered"]]
        out[method]={"cases":len(subset),"covered":len(covered),
                     "exact":sum(r["exact"] for r in subset),
                     "median_ns":int(median(r["median_ns"] for r in subset)),
                     "mean_mae_covered":None if not covered else str(sum((Fraction(r["mae"]) for r in covered),Fraction(0))/len(covered))}
    return out

if __name__=="__main__":
    import json
    print(json.dumps(summarize(evaluate()),indent=2))
