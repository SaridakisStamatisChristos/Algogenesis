import itertools
import random
import unittest
from compositional import Program,Stage,synthesize
from certificates import Polynomial,derive,equivalent,certificate

class CertificateTests(unittest.TestCase):
    def test_symbolic_proofs(self):
        tasks=[(lambda x,y:x*y+x,Polynomial((0,1,0,0,1,0))),
               (lambda x,y:x*y+y,Polynomial((0,0,1,0,1,0))),
               (lambda x,y:x*x+y*y,Polynomial((0,0,0,1,0,1))),
               (lambda x,y:x*x-y*y,Polynomial((0,0,0,1,0,-1)))]
        for oracle,target in tasks:
            result=synthesize(oracle,range(4))
            self.assertIsNotNone(result.program)
            self.assertTrue(equivalent(result.program,target))
            self.assertTrue(certificate(result.program,target)['equivalent'])
            for x,y in itertools.product(range(4,20),repeat=2):
                self.assertEqual(result.program.run(x,y),target.evaluate(x,y))

    def test_independent_polynomial_evaluation(self):
        rng=random.Random(45)
        stages=[Stage(c,o,v) for c in ('x','y') for o in ('add','sub') for v in ('x','y','one')]
        for _ in range(250):
            p=Program(rng.randrange(-5,6),tuple(rng.choice(stages) for _ in range(3)))
            poly=derive(p)
            for x,y in ((0,0),(0,7),(9,0),(2,5),(10,12)):
                self.assertEqual(p.run(x,y),poly.evaluate(x,y))

    def test_invalid_and_false_certificates(self):
        p=Program(0,(Stage('x','add','y'),))
        self.assertFalse(equivalent(p,Polynomial((0,0,0,0,0,0))))
        with self.assertRaises(ValueError): derive(Program(0,(Stage('z','add','y'),)))
        with self.assertRaises(ValueError): derive(Program(0,(Stage('x','mul','y'),)))

if __name__=='__main__': unittest.main()
