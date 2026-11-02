"""No-leakage real-world and synthetic evaluations of bounded expert advice.

Theoretical regret certificate concerns fixed bounded-range absolute loss.
Forecast accuracy comparisons are empirical and are NOT SOTA evidence.
"""
import json
from fractions import Fraction
from time import perf_counter_ns
from adaptive_forecast import evaluate as evaluate_v21
from real_world_validation import numeric_series
from regret_forecast import evaluate, tuned_eta
from stability_selector import evaluate as evaluate_gate

# The domains and seasonalities below are declared constants, not discovered
# from test values. Violations must raise, never auto-expand using future data.
HISTORICAL_CONFIG = {
    'nile_1871_1970': (0, 5000, 1),
    'sunspots_1700_2008': (0, 1000, 11),
    'macro_realgdp_quarterly': (0, 50000, 4),
    'macro_cpi_quarterly': (0, 1000, 4),
    'macro_unemp_quarterly': (0, 100, 4),
}


def historical_series():
    try:
        import statsmodels
        from statsmodels.datasets import macrodata, nile, sunspots
    except ImportError as error:
        raise RuntimeError('optional dependency: statsmodels is required') from error
    m = macrodata.load_pandas().data
    return {
        'nile_1871_1970': numeric_series(nile.load_pandas().data['volume']),
        'sunspots_1700_2008': numeric_series(sunspots.load_pandas().data['SUNACTIVITY']),
        'macro_realgdp_quarterly': numeric_series(m['realgdp']),
        'macro_cpi_quarterly': numeric_series(m['cpi']),
        'macro_unemp_quarterly': numeric_series(m['unemp']),
    }


def compare_sequence(values, *, lower, upper, season=11, warmup=32):
    values = tuple(values)
    if type(warmup) is not int or warmup < 32 or len(values) <= warmup:
        raise ValueError('warmup must be >=32 and leave evaluation observations')
    eta = tuned_eta(len(values)-warmup)
    start = perf_counter_ns()
    run = evaluate(values, lower=lower, upper=upper, warmup=warmup,
                   eta=eta, season=season)
    elapsed_ns = perf_counter_ns() - start
    previous = evaluate_v21(values, warmup=warmup)
    gated = evaluate_gate(values, warmup=warmup, season=season)
    if len(run.records) != len(previous.records) or len(run.records) != len(gated.records):
        raise AssertionError('evaluation windows differ')
    t = len(run.records)
    oracle = {name: sum((abs(dict(r.candidates)[name]-r.actual) for r in run.records), Fraction(0))/t
              for name in run.names}
    sample_naive = sum((abs(values[j]-values[j-1]) for j in range(1,warmup)), Fraction(0))/(warmup-1)
    selected = sum((abs(r.prediction-r.actual) for r in run.records), Fraction(0))/t
    cap = run.certificate()
    if not cap.valid:
        raise AssertionError('regret certificate failed')
    return {
        'evaluated': t,
        'eta': str(eta),
        'range': [str(lower), str(upper)],
        'mean_absolute_error': {
            'bounded_mw': float(selected),
            'v21_selector': float(previous.selected_mae),
            'stability_gate': float(gated.selected_mae),
            **{name: float(loss) for name,loss in oracle.items()}
        },
        'mase': None if sample_naive == 0 else {
            'bounded_mw': float(selected/sample_naive),
            'v21_selector': float(previous.selected_mae/sample_naive),
            'stability_gate': float(gated.selected_mae/sample_naive),
            **{name: float(loss/sample_naive) for name,loss in oracle.items()}
        },
        # Exact certificate is checked before serialization. Fraction strings
        # can exceed Python's safe digit-display limit; report compact metadata.
        'regret_normalized': float(cap.regret),
        'regret_numerator_bits': cap.regret.numerator.bit_length(),
        'regret_denominator_bits': cap.regret.denominator.bit_length(),
        'theoretical_upper_bound': str(cap.bound),
        'elapsed_ns': elapsed_ns,
    }


def benchmark_historical():
    return {name:compare_sequence(series,lower=HISTORICAL_CONFIG[name][0],
                                 upper=HISTORICAL_CONFIG[name][1],
                                 season=HISTORICAL_CONFIG[name][2])
            for name,series in historical_series().items()}


def benchmark_synthetic(seed=20261102, per_family=6, length=64):
    from adaptive_benchmark import challenge_sequences
    # Fixed grammar-derived maxima, independent of sampled series.
    configs={
        'quadratic':(-20000,20000,11),
        'exponential':(0,2**(2*length+4),11),
        'periodic':(-10,10,11),
        'impulse':(-100,length*length+100,11),
        'shift':(0,2**(3*length+4),11),
        'walk':(-5*length,5*length,11),
    }
    rows={}
    for name,seq in challenge_sequences(seed=seed,per_family=per_family,length=length).items():
        low,high,season = configs[name.rsplit('_',1)[0]]
        rows[name] = compare_sequence(seq,lower=low,upper=high,season=season)
    return rows


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--synthetic',action='store_true')
    args=parser.parse_args()
    data=benchmark_synthetic() if args.synthetic else benchmark_historical()
    print(json.dumps(data,indent=2,sort_keys=True))
