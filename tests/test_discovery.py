import itertools
import unittest
from algogenesis import run, zero_one_errors
from discovery import binary_state, discover, exact_search, verify, mutation
import random

class DiscoveryTests(unittest.TestCase):
    def test_independent_oracle_agrees(self):
        rng = random.Random(19)
        for width in range(2, 7):
            for _ in range(60):
                net = mutation(tuple(), width, rng, 15)
                for _ in range(12):
                    net = mutation(net, width, rng, 15)
                self.assertEqual(verify(net, width)['errors'], zero_one_errors(net, width))
    def test_exact_optimal(self):
        for width, expected in ((2, 1), (3, 3), (4, 5)):
            net = exact_search(width)
            self.assertEqual(len(net), expected)
            self.assertTrue(verify(net, width)['verified'])
            for perm in itertools.permutations(range(width)):
                self.assertEqual(run(net, perm), sorted(perm))
    def test_unseeded_reproducibility(self):
        a = discover(4, 300, 80, 42)
        self.assertEqual(a, discover(4, 300, 80, 42))
        self.assertFalse(a.seeded_with_baseline)
        self.assertEqual(a.errors, verify(a.network, 4)['errors'])
    def test_adversarial(self):
        self.assertFalse(verify(tuple(), 4)['verified'])
        self.assertRaises(ValueError, verify, ((0, 4),), 4)
        self.assertRaises(ValueError, exact_search, 5)
        self.assertRaises(ValueError, discover, 4, -1)

if __name__ == '__main__':
    unittest.main()
