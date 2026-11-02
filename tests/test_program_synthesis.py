import itertools
import unittest
from program_synthesis import Expr, evaluate, expression_search, synthesize, TASKS

class ProgramSynthesisTests(unittest.TestCase):
    def test_evaluation(self):
        e=Expr('abs',(Expr('sub',(Expr('var',value='x'),Expr('var',value='y'))),))
        self.assertEqual(evaluate(e, {'x':-5,'y':3}),8)
    def test_tasks(self):
        for name, oracle in TASKS.items():
            with self.subTest(task=name):
                result=synthesize(oracle,domain=range(-2,3),max_size=6)
                self.assertTrue(result.verified, result.as_dict())
                self.assertGreaterEqual(result.rounds,1)
                for x,y in itertools.product(range(-2,3),repeat=2):
                    self.assertEqual(evaluate(result.expression, {'x':x,'y':y}),oracle(x,y))
    def test_budget_and_input_validation(self):
        with self.assertRaises(ValueError):
            expression_search([], max_size=3)
        with self.assertRaises(ValueError):
            synthesize(lambda x,y:x+y, domain=[])
        with self.assertRaises(RuntimeError):
            expression_search([((1,2),3)],max_semantics=1)
    def test_no_solution_with_insufficient_size(self):
        result=synthesize(lambda x,y:x+y,domain=range(-2,3),max_size=1)
        self.assertFalse(result.verified)
    def test_counterexample_refines_spurious_solution(self):
        result=synthesize(lambda x,y:abs(x-y),domain=range(-2,3),max_size=6)
        self.assertTrue(result.verified)
        self.assertGreater(len(result.counterexamples),0)

if __name__=='__main__':
    unittest.main()
