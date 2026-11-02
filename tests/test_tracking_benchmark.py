import math,unittest
from fractions import Fraction
from regret_forecast import BoundedExperts
from switching_experts import FixedShareExperts,tuned_tracking_parameters
from tracking_benchmark import compare

class TrackingBenchmarkTests(unittest.TestCase):
    def test_switching_advantage(self):
        stream=[0]*100+[1]*100+[0]*100
        fixed=BoundedExperts(("zero","one"),lower=0,upper=1,eta=Fraction(1,4))
        track=FixedShareExperts(("zero","one"),lower=0,upper=1,eta=Fraction(1,4),share=Fraction(1,16))
        for y in stream:
            for machine in (fixed,track):
                machine.predict({"zero":0,"one":1});machine.observe(y)
        self.assertLess(sum(r.learner_loss for r in track.records),
                        sum(r.learner_loss for r in fixed.records)/2)
        path=track.best_switching_path(2)
        self.assertEqual(track.switching_certificate(path).comparator_loss,0)
        self.assertTrue(track.switching_certificate(path).valid)

    def test_heldout_mae_units(self):
        r=compare([2*n+3 for n in range(49)],lower=0,upper=1000,season=11,warmup=32,max_switches=2)
        self.assertEqual(r["n"],17)
        self.assertAlmostEqual(r["persistence_mae"],2)
        self.assertLessEqual(r["fixed_mae"],1000)
        self.assertLessEqual(r["tracking_mae"],1000)
        self.assertTrue(r["certificate_valid"])
        self.assertLessEqual(r["best_switch_path_mae"],r["persistence_mae"]+1e-9)
        eta,alpha=tuned_tracking_parameters(17,8,2)
        self.assertEqual(r["eta"],str(eta))
        self.assertEqual(r["share"],str(alpha))

    def test_parameter_validation(self):
        with self.assertRaises(ValueError):compare([3]*32,lower=0,upper=10)
        with self.assertRaises(ValueError):compare([3]*40,lower=0,upper=10,max_switches=-1)
        with self.assertRaises(ValueError):compare([30]*40,lower=0,upper=10)
        with self.assertRaises(TypeError):compare([True]*40,lower=0,upper=10)

    def test_optional_arima(self):
        try:import statsmodels
        except ImportError:self.skipTest("statsmodels optional")
        from statsmodels.datasets import nile
        seq=tuple(int(v) for v in nile.load_pandas().data["volume"])
        r=compare(seq,lower=0,upper=5000,season=1,with_arima=True)
        self.assertEqual(r["n"],68)
        self.assertTrue(math.isfinite(r["arima_110_mae"]))
        self.assertGreater(r["arima_110_mae"],0)
