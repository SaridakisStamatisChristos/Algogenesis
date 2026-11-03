import itertools
import random
import unittest
from experiments.sort_tournament import CANDIDATES

class SortingTournamentTests(unittest.TestCase):
    def test_exhaustive_small(self):
        for n in range(8):
            for xs in itertools.product((-2,0,2),repeat=n):
                for name,sort in CANDIDATES.items():
                    with self.subTest(n=n, xs=xs, algorithm=name):
                        original=list(xs)
                        self.assertEqual(sort(original),sorted(xs))
                        self.assertEqual(original,list(xs))
    def test_adversarial(self):
        rng=random.Random(1729)
        for n in (0,1,2,23,24,25,127,1024):
            samples=[list(range(n)),list(range(n,0,-1)),[0]*n,
                     [(-1)**i*(i//3) for i in range(n)],
                     [rng.randrange(-10**12,10**12) for _ in range(n)]]
            for xs in samples:
                for name,sort in CANDIDATES.items():
                    with self.subTest(n=n,algorithm=name):
                        self.assertEqual(sort(xs),sorted(xs))
if __name__=="__main__":unittest.main()
