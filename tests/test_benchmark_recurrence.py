import unittest
from benchmark_recurrence import benchmark

class BenchmarkHarnessTests(unittest.TestCase):
    def test_matched_prefix_and_heldout(self):
        records=benchmark(repeats=1,train=20)
        self.assertEqual(len(records),12)
        by_case={(r["case"],r["method"]):r for r in records}
        for case in ("fibonacci","cubic","geometric","tetrahedral","rational"):
            self.assertTrue(by_case[(case,"hankel")]["heldout_exact"],case)
            self.assertTrue(by_case[(case,"berlekamp_massey")]["heldout_exact"],case)
        self.assertFalse(by_case[("all_zero","hankel")]["heldout_exact"])
        self.assertTrue(by_case[("all_zero","berlekamp_massey")]["heldout_exact"])
        self.assertTrue(all(r["median_ns"]>=0 for r in records))
    def test_validation(self):
        with self.assertRaises(ValueError):benchmark(repeats=0)
        with self.assertRaises(ValueError):benchmark(train=2)
        with self.assertRaises(ValueError):benchmark(train=60)

if __name__=="__main__":unittest.main()
