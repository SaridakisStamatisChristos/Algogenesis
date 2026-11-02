import itertools
import unittest
from compositional import Stage, Program, synthesize, _predict

class CompositionalTests(unittest.TestCase):
    def test_two_loop_targets(self):
        tasks = [lambda x,y:x*y+x, lambda x,y:x*y+y,
                 lambda x,y:x*x+y*y, lambda x,y:2*x*y,
                 lambda x,y:x*x-y*y]
        for oracle in tasks:
            with self.subTest(oracle=oracle):
                result=synthesize(oracle,range(5))
                self.assertIsNotNone(result.program,result)
                self.assertEqual(result.verified_cases,25)
                for x,y in itertools.product(range(5),repeat=2):
                    self.assertEqual(result.program.run(x,y),oracle(x,y))

    def test_independent_interpreter_vs_semantics(self):
        stages=[Stage(c,o,v) for c in ('x','y') for o in ('add','sub') for v in ('x','y','one')]
        for first in stages:
            for second in stages:
                p=Program(-1,(first,second))
                for x,y in ((0,0),(0,4),(3,0),(2,3)):
                    self.assertEqual(p.run(x,y),_predict(p,(x,y)))

    def test_reproducibility(self):
        oracle=lambda x,y:x*x+y*y
        self.assertEqual(synthesize(oracle),synthesize(oracle))

    def test_limits_and_validation(self):
        with self.assertRaises(ValueError): synthesize(lambda x,y:x+y,[])
        with self.assertRaises(ValueError): synthesize(lambda x,y:x+y,[-1,0])
        with self.assertRaises(ValueError): synthesize(lambda x,y:x+y,max_stages=6)
        with self.assertRaises(TypeError): synthesize(lambda x,y:float(x+y))
        self.assertIsNone(synthesize(lambda x,y:x*x+y*y,max_stages=0).program)
        self.assertTrue(synthesize(lambda x,y:x*x+y*y,max_candidates=1).exhausted)

    def test_nonrepresentable(self):
        self.assertIsNone(synthesize(lambda x,y:x*x*x,max_stages=2).program)

if __name__ == '__main__':
    unittest.main()
