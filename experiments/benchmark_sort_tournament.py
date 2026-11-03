"""Reproducible paired-input benchmark; reports samples, median and population stdev."""
import argparse,json,random,statistics,time,platform
from experiments.sort_tournament import CANDIDATES
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--sizes",type=int,nargs="+",default=[100,1000,10000])
    p.add_argument("--repeats",type=int,default=11)
    p.add_argument("--seed",type=int,default=1729)
    args=p.parse_args()
    if args.repeats<2 or any(n<0 for n in args.sizes):p.error("invalid sizes/repeats")
    rng=random.Random(args.seed)
    records=[]
    for n in args.sizes:
        cases={"uniform":[rng.randrange(-n,n+1) for _ in range(n)],
               "sorted":list(range(n)),"reverse":list(range(n,0,-1)),
               "duplicates":[rng.randrange(4) for _ in range(n)]}
        for workload,values in cases.items():
            expected=sorted(values)
            for name,fn in {**CANDIDATES,"python_sorted":sorted}.items():
                samples=[]
                for _ in range(args.repeats):
                    start=time.perf_counter_ns();result=fn(values)
                    elapsed=time.perf_counter_ns()-start
                    if result!=expected:raise AssertionError((name,n,workload))
                    samples.append(elapsed)
                records.append(dict(n=n,workload=workload,algorithm=name,
                                    median_ns=statistics.median(samples),
                                    stdev_ns=statistics.pstdev(samples),
                                    samples_ns=samples))
    print(json.dumps({"seed":args.seed,"repeats":args.repeats,
                      "python":platform.python_version(),"platform":platform.platform(),
                      "records":records},indent=2))
if __name__=="__main__":main()
