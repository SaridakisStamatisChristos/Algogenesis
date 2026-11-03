"""Randomized-order sorting tournament with raw timings and bootstrap median intervals."""
import argparse
import json
import platform
import random
import statistics
import time
from experiments.sort_tournament import CANDIDATES


def median_interval(samples, rng, draws=2000):
    """Percentile bootstrap 95% interval for the sample median (not a guarantee)."""
    n = len(samples)
    medians = sorted(statistics.median(rng.choices(samples, k=n))
                     for _ in range(draws))
    return [medians[int(.025 * draws)], medians[int(.975 * draws)]]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sizes", type=int, nargs="+", default=[100, 1000, 10000])
    p.add_argument("--repeats", type=int, default=11)
    p.add_argument("--seed", type=int, default=1729)
    args = p.parse_args()
    if args.repeats < 2 or any(n < 0 for n in args.sizes):
        p.error("invalid sizes/repeats")
    rng = random.Random(args.seed)
    bootstrap_rng = random.Random(args.seed ^ 0xB0057)
    algorithms = {**CANDIDATES, "python_sorted": sorted}
    records = []
    for n in args.sizes:
        cases = {
            "uniform": [rng.randrange(-n, n + 1) for _ in range(n)],
            "sorted": list(range(n)),
            "reverse": list(range(n, 0, -1)),
            "duplicates": [rng.randrange(4) for _ in range(n)],
            "all_equal": [7] * n,
            "wide_range": [rng.randrange(-10**12, 10**12) for _ in range(n)],
        }
        for workload, values in cases.items():
            expected = sorted(values)
            samples = {name: [] for name in algorithms}
            # Warm each implementation and check its result before measurements.
            for name, fn in algorithms.items():
                if fn(values) != expected:
                    raise AssertionError(("warmup", name, n, workload))
            for _ in range(args.repeats):
                order = list(algorithms)
                rng.shuffle(order)
                for name in order:
                    start = time.perf_counter_ns()
                    result = algorithms[name](values)
                    elapsed = time.perf_counter_ns() - start
                    if result != expected:
                        raise AssertionError((name, n, workload))
                    samples[name].append(elapsed)
            for name, observations in samples.items():
                records.append({
                    "n": n, "workload": workload, "algorithm": name,
                    "median_ns": statistics.median(observations),
                    "mean_ns": statistics.mean(observations),
                    "stdev_ns": statistics.pstdev(observations),
                    "median_ci95_bootstrap_ns": median_interval(
                        observations, bootstrap_rng),
                    "samples_ns": observations,
                })
    print(json.dumps({
        "seed": args.seed, "repeats": args.repeats,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "method": "one warmup per candidate; randomized within-round order; "
                  "2000-resample percentile bootstrap for median",
        "records": records,
    }, indent=2))


if __name__ == "__main__":
    main()
