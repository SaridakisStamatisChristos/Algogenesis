import random
import unittest
from affine_transition import AffineTransition,synthesize,certify

class AffineTransitionTests(unittest.TestCase):
    def test_fibonacci(self):
        ref=AffineTransition(((0,1),(1,1)),(0,0))
        trace=tuple(ref.iterate((0,1),n) for n in range(9))
        result=synthesize(trace)
        self.assertEqual(result.transition,ref)
        self.assertTrue(certify(result.transition,ref))
        self.assertEqual(result.transition.power((0,1),100),ref.iterate((0,1),100))

    def test_three_interacting_registers(self):
        ref=AffineTransition(((1,1,0),(0,1,1),(0,0,1)),(0,0,1))
        trace=tuple(ref.iterate((0,0,0),n) for n in range(10))
        result=synthesize(trace)
        self.assertEqual(result.transition,ref)
        for n in (0,1,2,3,7,30,100):
            self.assertEqual(result.transition.power((0,0,0),n),ref.iterate((0,0,0),n))

    def test_random_matrix_power(self):
        rng=random.Random(1001)
        for d in (1,2,3,4):
            for _ in range(30):
                model=AffineTransition(tuple(tuple(rng.randint(-2,2) for _ in range(d)) for _ in range(d)),
                                       tuple(rng.randint(-2,2) for _ in range(d)))
                initial=tuple(rng.randint(-3,3) for _ in range(d))
                for n in (0,1,2,5,13):
                    self.assertEqual(model.power(initial,n),model.iterate(initial,n))

    def test_underdetermined_and_inconsistent(self):
        self.assertEqual(synthesize(((0,0),(0,0),(0,0))).reason,'underdetermined transition')
        self.assertEqual(synthesize(((0,),(1,),(3,),(8,))).reason,'inconsistent trace')

    def test_invalid_inputs(self):
        with self.assertRaises(ValueError):synthesize(((0,),))
        with self.assertRaises(ValueError):synthesize(((0,1),(2,)))
        with self.assertRaises(ValueError):AffineTransition(((1,),),(0,1))
        with self.assertRaises(ValueError):AffineTransition(((True,),),(0,))
        with self.assertRaises(ValueError):AffineTransition(((1,),),(0,)).power((0,),-1)
        self.assertFalse(certify(AffineTransition(((1,),),(0,)),AffineTransition(((1,),),(1,))))

if __name__=='__main__':unittest.main()
