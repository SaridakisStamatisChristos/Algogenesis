import unittest
from challenge_benchmark import challenges,evaluate,summarize

class ChallengeBenchmarkTests(unittest.TestCase):
    def test_reproducible_families(self):
        self.assertEqual(challenges(11),challenges(11))
        self.assertNotEqual(challenges(11),challenges(12))
        self.assertEqual(len(challenges()),36)
        self.assertTrue(all(len(s)==64 for s in challenges().values()))
    def test_no_leakage_and_matched_methods(self):
        rows=evaluate(repeats=1)
        self.assertEqual(len(rows),144)
        summary=summarize(rows)
        self.assertEqual(set(summary),{"hankel","berlekamp_massey","persistence","linear"})
        for method,metrics in summary.items():
            self.assertEqual(metrics["cases"],36)
            self.assertGreaterEqual(metrics["median_ns"],0)
        self.assertEqual(summary["berlekamp_massey"]["covered"],36)
        self.assertEqual(summary["hankel"]["exact"],30)
        self.assertEqual(summary["berlekamp_massey"]["exact"],30)
        self.assertEqual(summary["persistence"]["exact"],0)
    def test_reject_bad_parameters(self):
        for kwargs in ({"train":1},{"horizon":0},{"train":60,"horizon":8},{"repeats":0}):
            with self.assertRaises(ValueError):evaluate(**kwargs)
        with self.assertRaises(TypeError):evaluate(seed=1.2)

if __name__=="__main__":unittest.main()
