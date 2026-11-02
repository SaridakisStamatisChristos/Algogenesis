import random
import unittest
from advanced import prune, counterexample, prefix_beam, benchmark
from discovery import binary_state, verify, exact_search, mutation

class AdvancedTests(unittest.TestCase):
    def test_pruning_semantics(self):
        rng=random.Random(123)
        for width in range(2,7):
            for _ in range(40):
                net=()
                for _ in range(15):
                    net=mutation(net,width,rng,30)
                pruned=prune(net,width)
                self.assertEqual(binary_state(net,width),binary_state(pruned,width))
                self.assertLessEqual(len(pruned),len(net))
    def test_counterexamples(self):
        for width in range(2,7):
            self.assertIsNotNone(counterexample((),width))
        for width in range(2,5):
            self.assertIsNone(counterexample(exact_search(width),width))
    def test_beam(self):
        for width,depth in ((2,1),(3,3),(4,5)):
            result=prefix_beam(width,depth,beam=50000)
            self.assertIsNotNone(result)
            self.assertTrue(verify(result,width)['verified'])
            self.assertEqual(len(result),depth)
    def test_reproducibility(self):
        self.assertEqual(prefix_beam(4,5,128,42),prefix_beam(4,5,128,42))
        self.assertEqual(benchmark(3,range(2),20,16),benchmark(3,range(2),20,16))
    def test_invalid(self):
        with self.assertRaises(ValueError): prefix_beam(11,5)
        with self.assertRaises(ValueError): prefix_beam(4,-1)
        with self.assertRaises(ValueError): prefix_beam(4,5,0)
