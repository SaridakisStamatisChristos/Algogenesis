import random
import unittest
from math import comb
from coupled_recurrence import CoupledProgram,certify,synthesize

class CoupledRecurrenceTests(unittest.TestCase):
    def test_discovery_and_held_out(self):
        targets=[
            (lambda n:n**3,(0,1,6,6)),
            (lambda n:comb(n,3),(0,0,0,1)),
            (lambda n:n*(n-1)*(2*n-1)//6,(0,0,1,2)),
            (lambda n:7+3*n+2*comb(n,2)-comb(n,3),(7,3,2,-1)),
        ]
        for fn,coeff in targets:
            with self.subTest(coeff=coeff):
                result=synthesize(fn,range(9))
                self.assertIsNotNone(result.program,result)
                self.assertEqual(result.coefficients,coeff)
                self.assertTrue(certify(result.program,coeff))
                for n in (0,1,2,3,9,17,40,100):
                    self.assertEqual(result.program.run(n),fn(n))
                    self.assertEqual(result.program.predict(n),fn(n))

    def test_random_independent_interpreter(self):
        rng=random.Random(154)
        for _ in range(130):
            p=CoupledProgram(*(rng.randrange(-5,6) for _ in range(4)))
            for n in (0,1,2,3,7,14):
                self.assertEqual(p.run(n),p.predict(n))

    def test_reject_noncubic_oracle(self):
        result=synthesize(lambda n:n**4)
        self.assertIsNone(result.program)
        self.assertIn('contradicts',result.reason)

    def test_contract_and_budgets(self):
        with self.assertRaises(ValueError):synthesize(lambda n:n,range(3))
        with self.assertRaises(ValueError):synthesize(lambda n:n,[-1,0,1,2,3])
        with self.assertRaises(ValueError):synthesize(lambda n:n,max_coefficient=-1)
        with self.assertRaises(TypeError):synthesize(lambda n:float(n))
        with self.assertRaises(TypeError):CoupledProgram(0,0,0,True)
        with self.assertRaises(ValueError):CoupledProgram(0,0,0,0).run(-1)
        with self.assertRaises(ValueError):certify(CoupledProgram(0,0,0,0),(0,0,0))
        self.assertIsNone(synthesize(lambda n:n**3,max_coefficient=5).program)
        with self.assertRaises(Exception):CoupledProgram(0,0,0,0).run(10001)

    def test_deterministic(self):
        self.assertEqual(synthesize(lambda n:n**3),synthesize(lambda n:n**3))

if __name__=='__main__':unittest.main()
