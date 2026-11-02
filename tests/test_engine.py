import itertools
import unittest
from algogenesis import bubble_network, evolve, mutate, run, zero_one_errors
import random

class EngineTests(unittest.TestCase):
    def test_baselines(self):
        for n in range(2, 8):
            self.assertEqual(zero_one_errors(bubble_network(n), n), 0)
    def test_exhaustive_permutations(self):
        for n in range(2, 7):
            net = bubble_network(n)
            for perm in itertools.permutations(range(n)):
                self.assertEqual(run(net, perm), list(range(n)))
    def test_mutation_invariants(self):
        rng = random.Random(9)
        net = bubble_network(5)
        for _ in range(500):
            net = mutate(net, 5, rng)
            self.assertTrue(all(0 <= i < j < 5 for i, j in net))
    def test_reproducibility_and_correctness(self):
        a = evolve(4, 100, 32, 17)
        b = evolve(4, 100, 32, 17)
        self.assertEqual(a, b)
        self.assertEqual(a.errors, 0)
        self.assertLessEqual(len(a.best), a.baseline_comparators)
    def test_reject_invalid_width(self):
        with self.assertRaises(ValueError):
            evolve(1)

if __name__ == '__main__':
    unittest.main()
