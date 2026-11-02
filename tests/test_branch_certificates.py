import itertools
import random
import unittest
from branch_synthesis import Guard, Node, Affine, synthesize
from branch_certificates import CELLS, certify, leaf, branch

class BranchCertificatesTests(unittest.TestCase):
    def test_partition_basis(self):
        self.assertEqual(len(CELLS),13)
        self.assertEqual(sorted(map(len,CELLS.values())),[1]+[2]*6+[3]*6)

    def test_max_min_absdiff_and_clamp(self):
        targets=[
            (max,branch(Guard('x','lt','y'),leaf(0,1),leaf(1,0))),
            (min,branch(Guard('x','lt','y'),leaf(1,0),leaf(0,1))),
            (lambda x,y:abs(x-y),branch(Guard('x','lt','y'),leaf(-1,1),leaf(1,-1))),
            (lambda x,y:max(0,min(x,y)),
             branch(Guard('x','lt','zero'),leaf(),
                    branch(Guard('y','lt','zero'),leaf(),
                           branch(Guard('x','lt','y'),leaf(1,0),leaf(0,1)))))
        ]
        for oracle,reference in targets:
            with self.subTest(task=oracle):
                result=synthesize(oracle,range(-3,4))
                self.assertIsNotNone(result.program)
                proof=certify(result.program,reference)
                self.assertTrue(proof.equivalent,proof)
                for x,y in itertools.product((-1000,-10,0,3,20,1000),repeat=2):
                    self.assertEqual(result.program.run(x,y),reference.evaluate(x,y))

    def test_find_counterexample(self):
        proof=certify(leaf(1,0),leaf(0,1))
        self.assertFalse(proof.equivalent)
        x,y=proof.counterexample
        self.assertNotEqual(x,y)

    def test_random_semantically_equivalent_trees(self):
        rng=random.Random(43)
        for _ in range(120):
            a=leaf(rng.randrange(-2,3),rng.randrange(-2,3),rng.randrange(-2,3))
            g=Guard('x',rng.choice(('lt','le','eq')),'y')
            self.assertTrue(certify(a,branch(g,a,a)).equivalent)

    def test_reject_unsupported_guards_and_types(self):
        with self.assertRaises(ValueError):
            certify(branch(Guard('x','gt','y'),leaf(),leaf()),leaf())
        with self.assertRaises(TypeError):
            certify(Node(leaf=Affine(1.5,0,0)),leaf())

if __name__=='__main__':unittest.main()
