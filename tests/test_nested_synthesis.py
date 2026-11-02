import itertools
import random
import unittest
from nested_synthesis import Term,NestedProgram,synthesize,certify,BASIS

class NestedSynthesisTests(unittest.TestCase):
    def test_cubic_discovery(self):
        targets=[(lambda x,y:x**3,(3,0)),(lambda x,y:x*x*y,(2,1)),
                 (lambda x,y:x*y*y,(1,2)),(lambda x,y:y**3,(0,3))]
        for oracle,monomial in targets:
            with self.subTest(monomial=monomial):
                result=synthesize(oracle)
                self.assertIsNotNone(result.program,result)
                coefficients=[0]*10
                coefficients[BASIS.index(monomial)]=1
                self.assertTrue(certify(result.program,tuple(coefficients)))
                for x,y in itertools.product(range(4,11),repeat=2):
                    self.assertEqual(result.program.run(x,y),oracle(x,y))
    def test_sum_of_cubes(self):
        result=synthesize(lambda x,y:x**3+y**3)
        self.assertIsNotNone(result.program,result)
        expected=[0]*10
        expected[BASIS.index((3,0))]=1
        expected[BASIS.index((0,3))]=1
        self.assertTrue(certify(result.program,tuple(expected)))
    def test_interpreter_independent_from_polynomial(self):
        rng=random.Random(87)
        stages=[Term((a,b),v,s) for a in ('x','y') for b in ('x','y')
                for v in ('one','x','y') for s in (-1,1)]
        for _ in range(120):
            p=NestedProgram(rng.randrange(-3,4),tuple(rng.choice(stages) for _ in range(2)))
            for x,y in ((0,0),(0,4),(5,0),(2,3),(6,7)):
                predicted=sum(c*x**a*y**b for c,(a,b) in zip(p.polynomial(),BASIS))
                self.assertEqual(p.run(x,y),predicted)
    def test_negative_and_unrepresentable(self):
        r=synthesize(lambda x,y:-(x**3))
        self.assertIsNotNone(r.program)
        self.assertIsNone(synthesize(lambda x,y:x**4,max_terms=1).program)
        self.assertFalse(certify(r.program,(0,)*10))
    def test_resource_bounds(self):
        with self.assertRaises(ValueError): synthesize(lambda x,y:x,[])
        with self.assertRaises(ValueError): synthesize(lambda x,y:x,[-1,0])
        with self.assertRaises(ValueError): synthesize(lambda x,y:x,max_depth=3)
        with self.assertRaises(TypeError): synthesize(lambda x,y:1.2)
        self.assertTrue(synthesize(lambda x,y:x**3,max_candidates=1).exhausted)
        with self.assertRaises(ValueError): Term(('z',),'x')
        with self.assertRaises(ValueError): certify(NestedProgram(0,()),(0,))

if __name__=='__main__': unittest.main()
