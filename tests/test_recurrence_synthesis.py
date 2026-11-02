import random
import unittest
from recurrence_synthesis import Recurrence,synthesize,certify

class RecurrenceTests(unittest.TestCase):
    def test_discover_mutable_state_tasks(self):
        cases=[
            (lambda n:n*(n-1)//2,(0,0,1)),
            (lambda n:n*(n+1)//2,(0,1,1)),
            (lambda n:n*n,(0,1,2)),
            (lambda n:2*n*n+3*n+1,(1,5,4)),
        ]
        for oracle,coeff in cases:
            with self.subTest(coeff=coeff):
                result=synthesize(oracle,range(9),coefficient_bound=6)
                self.assertIsNotNone(result.program,result)
                self.assertTrue(certify(result.program,coeff))
                for n in (0,1,2,9,30,100):
                    self.assertEqual(result.program.run(n),oracle(n))
                    self.assertEqual(result.program.predict(n),oracle(n))

    def test_independent_interpreter_and_formula(self):
        rng=random.Random(91)
        for _ in range(150):
            p=Recurrence(rng.randrange(-5,6),rng.randrange(-5,6),
                         rng.randrange(-5,6),rng.choice((-1,1)))
            for n in (0,1,2,3,7,13):
                self.assertEqual(p.run(n),p.predict(n))

    def test_resource_and_type_validation(self):
        with self.assertRaises(ValueError):synthesize(lambda n:n,[])
        with self.assertRaises(ValueError):synthesize(lambda n:n,[-1,0])
        with self.assertRaises(ValueError):synthesize(lambda n:n,max_candidates=0)
        with self.assertRaises(TypeError):synthesize(lambda n:float(n))
        with self.assertRaises(TypeError):Recurrence(0,0,0,True)
        with self.assertRaises(ValueError):Recurrence(0,0,0,0)
        with self.assertRaises(ValueError):Recurrence(0,0,0).run(-1)
        with self.assertRaises(ValueError):certify(Recurrence(0,0,0),(0,0))
        self.assertTrue(synthesize(lambda n:n*n,max_candidates=1).exhausted)

    def test_insufficient_grammar_and_negative_certificate(self):
        self.assertIsNone(synthesize(lambda n:n*n*n,coefficient_bound=2).program)
        self.assertFalse(certify(Recurrence(0,0,1),(0,1,1)))

    def test_deterministic_replay(self):
        self.assertEqual(synthesize(lambda n:n*(n+1)//2),synthesize(lambda n:n*(n+1)//2))

if __name__=='__main__':unittest.main()
