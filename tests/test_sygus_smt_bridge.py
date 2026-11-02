"""Falsification tests for independent SMT-LIB verification of SyGuS text."""
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from sygus_clia import Unsupported, parse_problem, synthesize, output
from sygus_smt_bridge import build_smt_query, check_with_smt

FIXTURES = Path(__file__).resolve().parent.parent / 'benchmarks' / 'sygus_clia'


class SMTBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.max2 = (FIXTURES / 'max2.sl').read_text(encoding='utf-8')
        cls.diff = (FIXTURES / 'diff.sl').read_text(encoding='utf-8')
        cls.good_max2 = ('(define-fun mux_2 ((x Int) (y Int)) Int '
                         '(ite (< x y) y x))')
        cls.bad_max2 = '(define-fun mux_2 ((x Int) (y Int)) Int x)'

    def test_builds_unsat_counterexample_query_from_original_constraints(self):
        query = build_smt_query(self.max2, self.good_max2)
        self.assertIn('(set-logic QF_LIA)', query)
        self.assertIn('(define-fun mux_2', query)
        self.assertIn('(declare-const x Int)', query)
        self.assertIn('(declare-const y Int)', query)
        self.assertIn('(assert (not (and ', query)
        self.assertIn('(>= (mux_2 x y) x)', query)
        self.assertEqual(query.count('(check-sat)'), 1)
        self.assertTrue(query.endswith('(exit)\n'))

    def test_preserves_swapped_function_calls(self):
        solution = ('(define-fun f ((x Int) (y Int)) Int '
                    '(ite (< x y) (- y x) (- x y)))')
        query = build_smt_query(self.diff, solution)
        self.assertIn('(= (f x y) (f y x))', query)
        self.assertIn('(= (- x y) (f x y))', query)

    def test_negative_numerals_are_emitted_as_valid_smtlib(self):
        solution = '(define-fun mux_2 ((x Int) (y Int)) Int (+ (- 7) (- (+ x x x x x))))'
        query = build_smt_query(self.max2, solution)
        self.assertIn('Int (+ (- 7) (- (* 5 x)))', query)
        changed = self.max2.replace('(>= (mux_2 x y) x)',
                                    '(>= (mux_2 x y) (- 12))')
        self.assertIn('(>= (mux_2 x y) (- 12))',
                      build_smt_query(changed, solution))

    def test_rejects_unaccepted_input_without_solver_execution(self):
        malformed = self.max2.replace('(>= (mux_2 x y) x)',
                                      '(>= (* x y) (mux_2 x y))')
        with patch('sygus_smt_bridge.subprocess.run') as run:
            with self.assertRaises(Unsupported):
                check_with_smt(malformed, self.good_max2, solver='z3')
            run.assert_not_called()
        with self.assertRaises(Unsupported):
            build_smt_query(self.max2, self.good_max2 + '(exit)')
        with self.assertRaises((Unsupported, ValueError)):
            build_smt_query(self.max2, self.good_max2.replace('x y)', 'x ;y)'))

    @patch('sygus_smt_bridge.shutil.which', return_value='/usr/bin/z3')
    @patch('sygus_smt_bridge.subprocess.run')
    def test_solver_decision_table_is_fail_closed(self, run, _which):
        for stdout, expected in (('unsat\n', 'proved'), ('sat\n', 'counterexample'),
                                 ('unknown\n', 'unknown'), ('unsat\nsat\n', 'error'),
                                 ('(error "unexpected")\n', 'error'), ('', 'error')):
            with self.subTest(stdout=stdout):
                run.return_value = subprocess.CompletedProcess([], 0, stdout, '')
                result = check_with_smt(self.max2, self.good_max2, solver='z3')
                self.assertEqual(result.status, expected)
                argv = run.call_args.args[0]
                self.assertEqual(argv, ['z3', '-in', '-smt2'])
                self.assertIn('(check-sat)', run.call_args.kwargs['input'])
                self.assertNotIn('shell', run.call_args.kwargs)
        run.return_value = subprocess.CompletedProcess([], 1, 'unsat\n', 'error')
        self.assertEqual(check_with_smt(self.max2, self.good_max2, solver='z3').status,
                         'error')
        run.side_effect = subprocess.TimeoutExpired(['z3'], 0.5)
        self.assertEqual(check_with_smt(self.max2, self.good_max2, solver='z3').status,
                         'timeout')
        run.side_effect = FileNotFoundError()
        self.assertEqual(check_with_smt(self.max2, self.good_max2, solver='z3').status,
                         'unavailable')

    @patch('sygus_smt_bridge.shutil.which', return_value=None)
    def test_solver_missing_is_not_proof(self, _which):
        self.assertEqual(check_with_smt(self.max2, self.good_max2).status,
                         'unavailable')
        self.assertEqual(check_with_smt(self.max2, self.good_max2, solver='z3').status,
                         'unavailable')

    def test_invalid_budget_and_solver_configuration(self):
        for budget in (0, -1, float('nan'), 3601, True):
            with self.assertRaises(ValueError):
                check_with_smt(self.max2, self.good_max2,
                               timeout_seconds=budget)
        with self.assertRaises(ValueError):
            check_with_smt(self.max2, self.good_max2, solver='not-a-solver')

    def test_live_z3_all_pinned_tasks_and_wrong_candidate(self):
        if not shutil.which('z3'):
            self.skipTest('Z3 binary is not installed; CI installs it for this gate')
        for name in ('max2.sl', 'max3.sl', 'max4.sl', 'diff.sl'):
            with self.subTest(benchmark=name):
                source = (FIXTURES / name).read_text(encoding='utf-8')
                problem = parse_problem(source)
                result = synthesize(problem, max_depth=3)
                self.assertEqual(result.status, 'proved')
                independent = check_with_smt(source, output(problem, result),
                                             solver='z3', timeout_seconds=30)
                self.assertEqual(independent.status, 'proved', independent)
        wrong = check_with_smt(self.max2, self.bad_max2, solver='z3')
        self.assertEqual(wrong.status, 'counterexample', wrong)


if __name__ == '__main__':
    unittest.main()
