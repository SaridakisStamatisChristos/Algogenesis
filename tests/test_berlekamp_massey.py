import random
import unittest
from fractions import Fraction
from berlekamp_massey import infer

class BerlekampMasseyTests(unittest.TestCase):
    def test_fibonacci(self):
        seq=[0,1]
        for _ in range(35):seq.append(seq[-1]+seq[-2])
        result=infer(seq[:18])
        self.assertEqual(result.complexity,2)
        self.assertEqual(result.coefficients,(1,1))
        for n in range(18,len(seq)):
            self.assertEqual(result.predict_next(seq[:n]),seq[n])
    def test_polynomial_and_geometric(self):
        for f,order in ((lambda n:n**3,4),(lambda n:3*2**n,1)):
            seq=[f(n) for n in range(30)]
            result=infer(seq[:15])
            self.assertEqual(result.complexity,order)
            for n in range(15,30):
                self.assertEqual(result.predict_next(seq[:n]),seq[n])
    def test_zero_and_fraction(self):
        self.assertEqual(infer([0]*20).complexity,0)
        seq=[Fraction(1,2**n) for n in range(20)]
        self.assertEqual(infer(seq).coefficients,(Fraction(1,2),))
    def test_random_known_recurrences(self):
        rng=random.Random(10007)
        for _ in range(120):
            order=rng.randint(1,5)
            coeffs=[rng.randint(-3,3) for _ in range(order)]
            seq=[rng.randint(-4,4) for _ in range(order)]
            for n in range(order,40):
                seq.append(sum(coeffs[j]*seq[n-order+j] for j in range(order)))
            result=infer(seq[:25])
            for n in range(25,40):
                self.assertEqual(result.predict_next(seq[:n]),seq[n])
    def test_invalid_and_nonproof(self):
        with self.assertRaises(ValueError):infer([])
        with self.assertRaises(TypeError):infer([1,2.0,3])
        model=infer([1,1,2,3,5,8,13,21])
        self.assertNotEqual(model.predict_next([1,1,2,3,5,8,13,21]),999)

if __name__=="__main__":unittest.main()
