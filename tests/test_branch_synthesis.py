import itertools
import random
import unittest
from branch_synthesis import Affine, Guard, Node, synthesize

class BranchSynthesisTests(unittest.TestCase):
    def test_piecewise_tasks(self):
        tasks=[max,min,lambda x,y:abs(x-y),lambda x,y:max(0,min(x,y)),lambda x,y:1 if x<y else -1]
        for fn in tasks:
            with self.subTest(task=str(fn)):
                result=synthesize(fn,range(-3,4))
                self.assertIsNotNone(result.program,result)
                for x,y in itertools.product(range(-7,8),repeat=2):
                    self.assertEqual(result.program.run(x,y),fn(x,y))
    def test_independent_ast_vs_semantics(self):
        rng=random.Random(100)
        for _ in range(100):
            a=Node(leaf=Affine(rng.randint(-2,2),rng.randint(-2,2),rng.randint(-2,2)))
            b=Node(leaf=Affine(rng.randint(-2,2),rng.randint(-2,2),rng.randint(-2,2)))
            n=Node(guard=Guard('x',rng.choice(('lt','le','eq')),'y'),yes=a,no=b)
            for x,y in ((-5,0),(0,0),(3,-4),(2,9)):
                self.assertEqual(n.evaluate(x,y),n.run(x,y))
    def test_budget_validation(self):
        with self.assertRaises(ValueError):synthesize(max,[])
        with self.assertRaises(ValueError):synthesize(max,[0,1.5])
        with self.assertRaises(ValueError):synthesize(max,max_depth=5)
        with self.assertRaises(TypeError):synthesize(lambda x,y:float(x+y))
        self.assertIsNone(synthesize(lambda x,y:abs(x-y),max_depth=0).program)
        self.assertTrue(synthesize(max,max_partitions=1).exhausted)
    def test_reproducibility(self):
        self.assertEqual(synthesize(max),synthesize(max))
    def test_reject_malformed_ast(self):
        with self.assertRaises(ValueError):Node()
        with self.assertRaises(ValueError):Node(guard=Guard('x','lt','y'))

if __name__=='__main__':unittest.main()
