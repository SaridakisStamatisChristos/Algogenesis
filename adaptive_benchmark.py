"""Seeded prequential benchmark: exact per-case loss, float macro aggregation.

Six synthetic families: quadratic, exponential, periodic, impulse,
midstream regime switch, and random walk. The same forecast window is used
for all methods, without evaluation-label leakage. Not an external SOTA test.
"""
from math import fsum
from random import Random
from statistics import median
from time import perf_counter_ns
from adaptive_forecast import EXPERTS, evaluate


def challenge_sequences(seed=20261102, per_family=6, length=64):
    if any(type(x) is not int for x in (seed, per_family, length)):
        raise TypeError("seed, per_family and length must be integers")
    if per_family < 1 or length < 36:
        raise ValueError("positive sample count, length >= 36 required")
    rng = Random(seed)
    examples = {}
    for case in range(per_family):
        a = rng.randint(1, 4)
        b = rng.randint(-5, 5)
        examples[f"quadratic_{case}"] = tuple(a*t*t+b*t+2 for t in range(length))
        r = rng.randint(2, 4)
        examples[f"exponential_{case}"] = tuple(r**t for t in range(length))
        period = rng.randint(3, 7)
        phase = rng.randint(0, period-1)
        examples[f"periodic_{case}"] = tuple((t+phase)%period for t in range(length))
        offset = rng.randint(0, 6)
        examples[f"impulse_{case}"] = tuple(t*t+(rng.randint(-15,15) if t%7==offset else 0)
                                              for t in range(length))
        shift = rng.randint(34, 46)
        examples[f"shift_{case}"] = tuple(2**t if t<shift else 3**(t-shift)*2**shift
                                         for t in range(length))
        walk = [rng.randint(-3,3)]
        for t in range(1,length):
            walk.append(walk[-1]+rng.randint(-4,4))
        examples[f"walk_{case}"] = tuple(walk)
    return examples


def benchmark(seed=20261102, per_family=6, length=64, **kwargs):
    scores = []
    for name, seq in challenge_sequences(seed,per_family,length).items():
        start=perf_counter_ns()
        result=evaluate(seq,**kwargs)
        elapsed=perf_counter_ns()-start
        values=dict(result.candidate_relative_mae)
        values["adaptive"]=result.selected_relative_mae
        scores.append({"case":name,"family":name.rsplit("_",1)[0],
                       "losses":values,"switches":result.switches,"elapsed_ns":elapsed})
    return tuple(scores)


def summarize(scores):
    if not scores:raise ValueError("at least one benchmark record required")
    families=sorted({r["family"] for r in scores})
    methods=("adaptive",)+EXPERTS
    output={}
    for family in families+["overall"]:
        subset=[r for r in scores if r["family"]==family] if family!="overall" else list(scores)
        output[family]={
            "count":len(subset),
            "mean_relative_loss":{name:fsum(float(r["losses"][name]) for r in subset)/len(subset)
                                  for name in methods},
            "median_elapsed_ns":int(median(r["elapsed_ns"] for r in subset)),
        }
    return output


if __name__=="__main__":
    import json
    print(json.dumps(summarize(benchmark()),indent=2))
