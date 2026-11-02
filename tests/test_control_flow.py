import unittest
from control_flow import IntExpr as E, Predicate as P, Statement as S, Interpreter, FuelExhausted

class ControlFlowTests(unittest.TestCase):
    def test_branch(self):
        x,y=E('register',atom='x'),E('register',atom='y')
        program=(S('if',condition=P('lt',x,y),body=(S('assign',name='x',expr=y),)),)
        self.assertEqual(Interpreter().run(program,{'x':2,'y':7})['x'],7)
        self.assertEqual(Interpreter().run(program,{'x':8,'y':7})['x'],8)
    def test_loop(self):
        x=E('register',atom='x')
        program=(S('repeat',count=5,body=(S('assign',name='x',expr=E('add',(x,E('literal',atom=2)))),)),)
        self.assertEqual(Interpreter().run(program,{'x':1})['x'],11)
        with self.assertRaises(FuelExhausted):
            Interpreter(fuel=3).run(program,{'x':1})
    def test_bad_inputs_and_loops(self):
        with self.assertRaises(TypeError):
            Interpreter().run((),{'x':True})
        with self.assertRaises(ValueError):
            Interpreter().run((S('repeat',count=-1),),{})
        with self.assertRaises(ValueError):
            Interpreter().run((S('repeat',count=10001),),{})
        with self.assertRaises(ValueError):
            Interpreter().run((S('unexpected'),),{})

if __name__=='__main__': unittest.main()
