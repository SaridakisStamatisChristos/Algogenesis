import itertools
import unittest
from branch_synthesis import Guard
from branch_certificates import branch,leaf,certify
from exact_cegis import synthesize_exact

class ExactCegisTests(unittest.TestCase):
    def test_exact_tasks(self):
        targets=[
            branch(Guard('x','lt','y'),leaf(0,1),leaf(1,0)),
            branch(Guard('x','lt','y'),leaf(1,0),leaf(0,1)),
            branch(Guard('x','lt','y'),leaf(-1,1),leaf(1,-1)),
            branch(Guard('x','lt','zero'),leaf(),
                   branch(Guard('y','lt','zero'),leaf(),
                          branch(Guard('x','lt','y'),leaf(1,0),leaf(0,1)))
        ]
        for reference in targets:
            with self.subTest(reference=reference):
                result=synthesize_exact(reference)
                self.assertIsNotNone(result.program,result)
                self.assertTrue(result.certificate.equivalent)
                self.assertTrue(certify(result.program,reference).equivalent)
                for x,y in itertools.product((-1000,-9,0,2,999),repeat=2):
                    self.assertEqual(result.program.run(x,y),reference.evaluate(x,y))

    def test_counterexample_guidance(self):
        reference=branch(Guard('x','lt','y'),leaf(-1,1),leaf(1,-1))
        result=synthesize_exact(reference)
        self.assertTrue(result.certificate.equivalent)
        self.assertGreater(len(result.counterexamples),0)

    def test_insufficient_grammar(self):
        reference=branch(Guard('x','lt','y'),leaf(-1,1),leaf(1,-1))
        result=synthesize_exact(reference,max_depth=0)
        self.assertIsNone(result.program)
        self.assertFalse(result.exhausted)

    def test_budget_exhaustion(self):
        reference=branch(Guard('x','lt','y'),leaf(0,1),leaf(1,0))
        result=synthesize_exact(reference,max_partitions=1)
        self.assertIsNone(result.program)
        self.assertTrue(result.exhausted)

    def test_validation_and_reproducibility(self):
        ref=branch(Guard('x','lt','y'),leaf(0,1),leaf(1,0))
        self.assertEqual(synthesize_exact(ref),synthesize_exact(ref))
        with self.assertRaises(ValueError):synthesize_exact(ref,initial_examples=())
        with self.assertRaises(ValueError):synthesize_exact(ref,max_depth=5)
        with self.assertRaises(ValueError):synthesize_exact(ref,max_rounds=0)
        with self.assertRaises(ValueError):synthesize_exact(ref,initial_examples=((1,2.0),))

if __name__=='__main__':unittest.main()
