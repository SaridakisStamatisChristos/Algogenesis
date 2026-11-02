"""Reproducible exact-recurrence inference comparison; not a SOTA claim.

Run: python benchmark_recurrence.py
No training on the held-out suffix. Both solvers use the same prefix.
Wall-clock timings are platform-dependent; do not compare across machines.
"""
from fractions import Fraction
from math import comb
from statistics import median
from time import perf_counter_ns
from observable_recurrence import synthesize
from berlekamp_massey import infer

def cases():
    return {
        "fibonacci": _fibonacci(60),
        "cubic": tuple(n**3 for n in range(60)),
        "geometric": tuple(3*2**n for n in range(60)),
        "tetrahedral": tuple(comb(n,3) for n in range(60)),
        "rational": tuple(Fraction(1,2**n) for n in range(60)),
        "all_zero": (0,)*60,
    }

def _fibonacci(count):
    out=[0,1]
    while len(out)<count:out.append(out[-1]+out[-2])
    return tuple(out[:count])

def benchmark(*,repeats=5,train=30):
    if type(repeats) is not int or repeats<1:raise ValueError("positive repeats required")
    if type(train) is not int or train<3:raise ValueError("train must be >=3")
    records=[]
    for name,seq in cases().items():
        if train>=len(seq):raise ValueError("training window must leave held-out observations")
        prefix=seq[:train]
        for method in ("hankel","berlekamp_massey"):
            def run():
                if method=="hankel":
                    d=synthesize(prefix)
                    if d.model is None:return None,d.order
                    return d.model.generate(len(seq))[train:],d.order
                d=infer(prefix)
                if d.complexity==0:return (Fraction(0),)*(len(seq)-train),0
                history=list(prefix)
                while len(history)<len(seq):
                    history.append(d.predict_next(history))
                return tuple(history[train:]),d.complexity
            durations=[]
            result=None
            for _ in range(repeats):
                start=perf_counter_ns()
                result=run()
                durations.append(perf_counter_ns()-start)
            prediction,order=result
            exact=prediction is not None and tuple(prediction)==seq[train:]
            records.append({"case":name,"method":method,"order":order,
                            "heldout_exact":exact,"median_ns":int(median(durations))})
    return tuple(records)

if __name__=="__main__":
    import json
    print(json.dumps(benchmark(),indent=2))
