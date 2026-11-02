import unittest
from dynamic_synthesis import synthesize, DynamicProgram
from control_flow import FuelExhausted

class DynamicSynthesisTests(unittest.TestCase):
    def test_multiplication(self):
        report = synthesize(lambda x, y: x * y)
        self.assertIsNotNone(report.program)
        for x in range(7):
            for y in range(7):
                self.assertEqual(report.program.run(x, y), x * y)

    def test_negative_multiplication(self):
        report = synthesize(lambda x, y: -(x * y))
        self.assertIsNotNone(report.program)
        for x in range(7):
            for y in range(7):
                self.assertEqual(report.program.run(x, y), -(x * y))

    def test_unrepresentable(self):
        report = synthesize(lambda x, y: x*x + y*y)
        self.assertIsNone(report.program)

    def test_fuel(self):
        program = DynamicProgram(0, 'x', 'y', 'add')
        with self.assertRaises(FuelExhausted):
            program.run(100, 2, fuel=2)

    def test_bad_domain(self):
        with self.assertRaises(ValueError):
            synthesize(lambda x, y: x+y, domain=[])

if __name__ == '__main__':
    unittest.main()
