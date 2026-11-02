import unittest
from fractions import Fraction
from real_world_validation import numeric_series,evaluate_series,run_statsmodels

class RealWorldValidationTests(unittest.TestCase):
    def test_exact_decimal_inputs(self):
        self.assertEqual(numeric_series([0.1,1.25,3]),
                         (Fraction(1,10),Fraction(5,4),Fraction(3)))

    def test_seasonal_naive_manual_oracle(self):
        seq=[float(n%5) for n in range(50)]
        result=evaluate_series(seq,period=5)
        self.assertEqual(result["observations"],50)
        self.assertEqual(result["evaluated"],18)
        self.assertEqual(result["mean_relative_error"]["seasonal_naive_5"],0)
        self.assertEqual(result["mean_relative_error"]["bm_long"],0)

    def test_validation(self):
        for observations in ([float('nan')]*40,[float('inf')]*40,[True]*40,[None]*40):
            with self.assertRaises((ValueError,TypeError)):numeric_series(observations)
        with self.assertRaises(ValueError):evaluate_series([1]*40,period=0)
        with self.assertRaises(ValueError):evaluate_series([1]*40,period=33)
        with self.assertRaises(ValueError):evaluate_series([1]*15)

    def test_real_data_if_available(self):
        try:import statsmodels
        except ImportError:self.skipTest("optional statsmodels not available")
        result=run_statsmodels()["datasets"]
        self.assertEqual(result["nile_annual_flow_1871_1970"]["observations"],100)
        self.assertEqual(result["annual_sunspots_1700_2008"]["observations"],309)
        for record in result.values():
            self.assertEqual(record["evaluated"],record["observations"]-32)
            self.assertGreaterEqual(record["mean_relative_error"]["adaptive"],0)
