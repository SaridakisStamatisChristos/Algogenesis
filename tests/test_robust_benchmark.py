import unittest
from robust_benchmark import challenge_cases,benchmark,summarize

class RobustBenchmarkTests(unittest.TestCase):
    def test_shift_is_visible_to_forecast(self):
        train=32;horizon=8
        cases=challenge_cases(train=train,horizon=horizon)
        self.assertEqual(len(cases),40)
        for name,seq in cases.items():
            self.assertEqual(len(seq),train+horizon)
            if name.startswith("regime_"):
                self.assertTrue(any(seq[n]==3**n for n in range(train,train+horizon)))
                self.assertTrue(all(seq[n]==2**n for n in range(train)))
    def test_reproducible_and_seed_sensitive(self):
        self.assertEqual(challenge_cases(seed=19),challenge_cases(seed=19))
        self.assertNotEqual(challenge_cases(seed=19),challenge_cases(seed=20))
    def test_benchmark_detects_nonstationarity(self):
        rows=benchmark(repeats=1)
        self.assertEqual(len(rows),160)
        metrics=summarize(rows)
        self.assertEqual(metrics["bm"]["covered"],40)
        self.assertEqual(metrics["hankel"]["covered"],40)
        self.assertEqual(metrics["bm"]["exact"],32)
        self.assertEqual(metrics["hankel"]["exact"],32)
        self.assertTrue(all(not r["exact"] for r in rows if r["family"]=="regime"))
        self.assertEqual(metrics["persistence"]["exact"],0)
        self.assertTrue(all(r["median_ns"]>=0 for r in rows))
    def test_invalid(self):
        with self.assertRaises(ValueError):challenge_cases(train=4)
        with self.assertRaises(ValueError):challenge_cases(horizon=3)
        with self.assertRaises(TypeError):challenge_cases(seed=1.5)
        with self.assertRaises(ValueError):benchmark(repeats=0)

if __name__=="__main__":unittest.main()
