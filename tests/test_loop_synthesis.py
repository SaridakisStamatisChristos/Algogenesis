import unittest
from loop_synthesis import LoopCandidate,synthesize_loop

class LoopTests(unittest.TestCase):
    def test_multiplication(self):
        r=synthesize_loop(lambda x,y:x*y)
        self.assertIsNotNone(r.candidate)
        self.assertEqual(r.verified_cases,49)
        for x in range(7):
            for y in range(7): self.assertEqual(r.candidate.run(x,y),x*y)
    def test_negative_multiplication(self):
        r=synthesize_loop(lambda x,y:-(x*y))
        self.assertIsNotNone(r.candidate)
    def test_reject_unexpressible(self):
        r=synthesize_loop(lambda x,y:x*x+y*y)
        self.assertIsNone(r.candidate)
    def test_bad_domain(self):
        with self.assertRaises(ValueError): synthesize_loop(lambda x,y:x+y,range(-1,2))
    def test_determinism(self):
        a=synthesize_loop(lambda x,y:x*y)
        b=synthesize_loop(lambda x,y:x*y)
        self.assertEqual(a,b)
    def test_fuel_limit(self):
        from control_flow import FuelExhausted
        with self.assertRaises(FuelExhausted): LoopCandidate(0,'addy','x').run(1000,2)

if __name__=='__main__':unittest.main()
