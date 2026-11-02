import unittest
from fractions import Fraction
from observable_recurrence import synthesize, LinearRecurrence, certify

class ObservableRecurrenceTests(unittest.TestCase):
    def test_fibonacci_scalar_hidden_state(self):
        seq=[0,1]
        for _ in range(25):seq.append(seq[-1]+seq[-2])
        found=synthesize(seq[:15])
        self.assertEqual(found.order,2)
        self.assertEqual(found.model.coefficients,(Fraction(1),Fraction(1)))
        self.assertEqual(found.model.generate(len(seq)),tuple(seq))

    def test_geometric_and_cubic(self):
        seq=[3*2**n for n in range(20)]
        found=synthesize(seq[:12])
        self.assertEqual(found.order,1)
        self.assertEqual(found.model.generate(20),tuple(seq))
        cubic=[n**3 for n in range(25)]
        found=synthesize(cubic[:16])
        self.assertEqual(found.order,4)
        self.assertEqual(found.model.generate(25),tuple(cubic))

    def test_rational_recurrence(self):
        m=LinearRecurrence((Fraction(1,2),),(Fraction(8),))
        found=synthesize(m.generate(10))
        self.assertTrue(certify(m,found.model))
        self.assertEqual(found.model.generate(15),m.generate(15))

    def test_falsification_and_insufficient_data(self):
        self.assertIsNone(synthesize([0]*12).model)
        self.assertIsNone(synthesize([n*n for n in range(12)],max_order=1).model)
        self.assertIsNone(synthesize([0,1,0,1,0,1,0,1],max_order=1).model)
        with self.assertRaises(ValueError):synthesize([1,2])
        with self.assertRaises(ValueError):synthesize([1,2,3],max_order=0)
        with self.assertRaises(TypeError):synthesize([1,2,3.0])
        with self.assertRaises(ValueError):LinearRecurrence((1,2),(0,))
        with self.assertRaises(ValueError):LinearRecurrence((1,),(0,)).generate(-1)

    def test_finite_trace_is_not_universal_proof(self):
        # A polynomial can match the first 12 Fibonacci observations
        # yet diverge later: this cannot be distinguished from samples.
        seq=[0,1]
        for _ in range(15):seq.append(seq[-1]+seq[-2])
        model=synthesize(seq[:12]).model
        self.assertIsNotNone(model)
        adversary=seq[:12]+[999999]
        self.assertNotEqual(model.generate(13),tuple(adversary))

if __name__=='__main__':unittest.main()
