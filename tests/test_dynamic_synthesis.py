import unittest
from dynamic_synthesis import DynamicProgram, synthesize
from control_flow import Statement, IntExpr, Interpreter, FuelExhausted

class DynamicTests(unittest.TestCase):
    def test_mul(self):
        r=synthesize(lambda x,y:x*y)
        self.assertIsNotNone(r.program)
        self.assertEqual(r.verified_cases,49)
        for x in range(7):
            for y in range(7): self.assertEqual(r.program.run(x,y),x*y)
    def test_neg_mul(self):
        r=synthesize(lambda x,y:-(x*y))
        self.assertIsNotNone(r.program)
    def test_unrepresentable(self):
        self.assertIsNone(synthesize(lambda x,y:x*x+y*y).program)
    def test_determinism(self):
        self.assertEqual(synthesize(lambda x,y:x*y),synthesize(lambda x,y:x*y))
    def test_dynamic_ast_same_for_all_inputs(self):
        p=DynamicProgram(0,'x','y','add')
        self.assertEqual(p.ast(),p.ast())
        self.assertEqual(p.run(3,4),12)
        self.assertEqual(p.run(5,2),10)
    def test_negative_count_rejected(self):
        with self.assertRaises(ValueError): DynamicProgram(0,'x','y','add').run(-1,2)
    def test_fuel_enforced(self):
        with self.assertRaises(FuelExhausted): DynamicProgram(0,'x','y','add').run(200,1,fuel=10)
    def test_invalid_domain(self):
        with self.assertRaises(ValueError): synthesize(lambda x,y:x*y,[-1,0])
    def test_round_budget(self):
        r=synthesize(lambda x,y:x*y,max_rounds=1)
        self.assertEqual(r.rounds,1)
    def test_literal_repeat_backcompat(self):
        p=(Statement('repeat',count=3,body=(Statement('assign',name='a',expr=IntExpr('add',(IntExpr('register',atom='a'),IntExpr('literal',atom=1)))),)),)
        self.assertEqual(Interpreter().run(p,{'a':0})['a'],3)

if __name__=='__main__': unittest.main()
