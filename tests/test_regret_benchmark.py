import unittest
from fractions import Fraction
from regret_benchmark import compare_sequence, benchmark_synthetic, historical_series, HISTORICAL_CONFIG


class RegretBenchmarkTests(unittest.TestCase):
    def test_heldout_metrics_exactly_recomputable(self):
        seq=[n*n+n for n in range(49)]
        results=compare_sequence(seq,lower=0,upper=3000)
        self.assertEqual(results['evaluated'],17)
        self.assertLessEqual(results['mean_absolute_error']['bm_long'],3000/1024)
        self.assertLessEqual(results['mean_absolute_error']['bm_short'],3000/1024)
        step=Fraction(3000,2**256)
        def independent_round(value):
            ticks=Fraction(value,1)/step
            return step*((2*ticks.numerator+ticks.denominator)//(2*ticks.denominator))
        expected=sum(abs(independent_round(seq[n-1])-seq[n]) for n in range(32,49))/17
        self.assertEqual(results['mean_absolute_error']['persistence'],float(expected))
        self.assertGreaterEqual(results['mase']['bm_long'],0)

    def test_synthetic_fixed_bounded_protocol(self):
        rows=benchmark_synthetic(seed=999,per_family=1)
        self.assertEqual(len(rows),6)
        for row in rows.values():
            self.assertEqual(row['evaluated'],32)
            self.assertIsNotNone(row['mase'])
            self.assertGreater(row['elapsed_ns'],0)

    def test_optional_datasets_if_available(self):
        try:
            from statsmodels.datasets import nile, sunspots, macrodata
        except ImportError:
            self.skipTest('optional statsmodels unavailable')
        streams=historical_series()
        self.assertEqual(len(streams),5)
        self.assertEqual(len(streams['nile_1871_1970']),100)
        self.assertEqual(len(streams['sunspots_1700_2008']),309)
        self.assertEqual(len(streams['macro_unemp_quarterly']),203)
        for name,series in streams.items():
            lo,hi,_=HISTORICAL_CONFIG[name]
            self.assertTrue(all(lo <= v <= hi for v in series))

    def test_invalid_and_no_data_dependent_bound_expansion(self):
        with self.assertRaises(ValueError):compare_sequence([0]*32,lower=0,upper=1)
        with self.assertRaises(ValueError):compare_sequence([2]*40,lower=0,upper=1)
        with self.assertRaises(ValueError):compare_sequence([0]*40,lower=1,upper=0)
