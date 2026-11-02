import unittest
from fractions import Fraction
from adaptive_benchmark import benchmark, challenge_sequences, summarize

class AdaptiveBenchmarkTests(unittest.TestCase):
    def test_reproducibility(self):
        left=challenge_sequences(seed=21,per_family=2)
        self.assertEqual(left,challenge_sequences(seed=21,per_family=2))
        self.assertNotEqual(left,challenge_sequences(seed=22,per_family=2))
        self.assertEqual(len(left),12)
        self.assertTrue(all(len(x)==64 for x in left.values()))

    def test_matched_exact_metrics(self):
        records=benchmark(seed=42,per_family=2)
        self.assertEqual(len(records),12)
        summary=summarize(records)
        self.assertEqual(summary["overall"]["count"],12)
        self.assertEqual(len(summary),7)
        for record in records:
            self.assertEqual(len(record["losses"]),5)
            self.assertTrue(all(type(v) is Fraction and v>=0
                                for v in record["losses"].values()))

    def test_regime_and_noise_not_overclaimed(self):
        seq=challenge_sequences(seed=10,per_family=1)
        self.assertTrue(any(any(v[n]!=2*v[n-1] for n in range(34,48))
                            for k,v in seq.items() if k.startswith("shift_")))
        result=summarize(benchmark(seed=10,per_family=1))
        self.assertGreater(result["shift"]["mean_relative_loss"]["adaptive"],0)
        self.assertGreater(result["impulse"]["mean_relative_loss"]["adaptive"],0)

    def test_validation(self):
        with self.assertRaises(TypeError):challenge_sequences(seed=2.5)
        with self.assertRaises(ValueError):challenge_sequences(per_family=0)
        with self.assertRaises(ValueError):challenge_sequences(length=30)
        with self.assertRaises(ValueError):summarize([])
