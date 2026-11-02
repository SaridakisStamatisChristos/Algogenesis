"""v1.9 — rigorous forecasting challenge with visible distribution shifts.

Separate smooth, periodic, impulse-noise, and visible regime-shift
families. The shift must occur inside the held-out interval.
Exact recurrence fitting is intentionally not expected to win every case.
"""
from fractions import Fraction
from random import Random
from statistics import median
from time import perf_counter_ns
from observable_recurrence import synthesize
from berlekamp_massey import infer

def challenge_cases(seed=20261102,train=32,horizon=8):
    if type(seed) is not int or type(train) is not int or type(horizon) is not int:
        raise TypeError("integer parameters required")
    if train<10 or horizon<4:raise ValueError("train>=10 and horizon>=4 required")
    rng=Random(seed)
    length=train+horizon
    cases={}
    for i in range(8):
        a=rng.randint(1,5);b=rng.randint(-4,4)
        cases[f"polynomial_{i}"]=tuple(a*n*n+b*n+2 for n in range(length))
    for i in range(8):
        base=rng.randint(2,4)
        cases[f"exponential_{i}"]=tuple(base**n for n in range(length))
    for i in range(8):
        period=rng.randint(3,7);phase=rng.randint(0,period-1)
        cases[f"periodic_{i}"]=tuple((n+phase)%period for n in range(length))
    for i in range(8):
        offset=rng.randint(0,4)
        cases[f"impulse_{i}"]=tuple(2**n+(7 if n%5==offset else 0) for n in range(length))
    for i in range(8):
        switch=train+rng.randint(0,horizon-1)
        assert train<=switch<length
        cases[f"regime_{i}"]=tuple(2**n if n<switch else 3**n for n in range(length))
    return cases

def _predict(prefix,horizon,method):
    if method=="hankel":
        fitted=synthesize(prefix)
        return None if fitted.model is None else fitted.model.generate(len(prefix)+horizon)[-horizon:]
    if method=="bm":
        model=infer(prefix)
        if model.complexity==0:return (Fraction(0),)*horizon
        history=list(prefix)
        for _ in range(horizon):history.append(model.predict_next(history))
        return tuple(history[-horizon:])
    if method=="persistence":return (prefix[-1],)*horizon
    if method=="linear":
        d=prefix[-1]-prefix[-2]
        return tuple(prefix[-1]+(j+1)*d for j in range(horizon))
    raise ValueError("unknown method")

def benchmark(seed=20261102,train=32,horizon=8,repeats=3):
    if type(repeats) is not int or repeats<1:raise ValueError("positive repeats required")
    records=[]
    for name,series in challenge_cases(seed,train,horizon).items():
        prefix=series[:train];actual=series[train:]
        for method in ("hankel","bm","persistence","linear"):
            times=[]
            for _ in range(repeats):
                start=perf_counter_ns()
                predicted=_predict(prefix,horizon,method)
                times.append(perf_counter_ns()-start)
            mae=None if predicted is None else sum((abs(Fraction(x)-Fraction(y)) for x,y in zip(actual,predicted)),Fraction(0))/horizon
            records.append({"case":name,"family":name.rsplit("_",1)[0],"method":method,
                            "covered":predicted is not None,"exact":predicted is not None and tuple(predicted)==actual,
                            "mae":mae,"median_ns":int(median(times))})
    return tuple(records)

def summarize(records):
    summary={}
    for method in ("hankel","bm","persistence","linear"):
        rows=[r for r in records if r["method"]==method]
        covered=[r for r in rows if r["covered"]]
        summary[method]={"cases":len(rows),"covered":len(covered),
                         "exact":sum(r["exact"] for r in rows),
                         "mean_mae_covered":None if not covered else sum((r["mae"] for r in covered),Fraction(0))/len(covered),
                         "median_ns":int(median(r["median_ns"] for r in rows))}
    return summary

if __name__=="__main__":
    import json
    print(json.dumps(summarize(benchmark()),default=str,indent=2))
