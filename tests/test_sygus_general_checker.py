"""Adversarial external-solver validation on original pinned SyGuS problems."""
from pathlib import Path
import shutil
import unittest

from sygus_clia import Unsupported
from sygus_general_checker import build_external_query,check_external_solution

ROOT=Path(__file__).resolve().parent.parent
OLD=ROOT/'benchmarks'/'sygus_clia'
NEW=ROOT/'benchmarks'/'sygus_clia_v27'


class GeneralCheckerTests(unittest.TestCase):
    def test_cvc5_let_and_affine_guard_retain_original_max_constraints(self):
        source=(OLD/'max2.sl').read_text()
        text='(define-fun mux_2 ((x Int) (y Int)) Int (let ((_let_1 (+ x (* (- 1) y)))) (ite (>= _let_1 0) x y)))'
        q=build_external_query(source,text)
        self.assertIn('(let ((_let_1',q)
        self.assertIn('(assert (not (and ',q)
        if shutil.which('z3'):
            self.assertEqual(check_external_solution(source,text).status,'proved')

    def test_reject_forged_commands(self):
        source=(OLD/'max2.sl').read_text()
        candidate='(define-fun mux_2 ((x Int) (y Int)) Int x)'
        for bad in (source+'(assert false)',
                    source.replace('(check-synth)','(check-synth) (set-option :produce-models true)'),
                    source.replace('(set-logic LIA)','(set-logic BV)')):
            with self.subTest(case=bad[-45:]):
                with self.assertRaises(Unsupported):
                    build_external_query(bad,candidate)
        for bad in (candidate+' (exit)',
                    candidate.replace('mux_2','unexpected'),
                    candidate.replace('((x Int) (y Int))','((x Int) (z Int))'),
                    '(define-fun mux_2 ((x Int) (y Int)) Int (* x y)) (exit)',
                    candidate.replace(' Int x)', ' Int (unknown_fn x))')):
            with self.subTest(case=bad[-45:]):
                with self.assertRaises(Unsupported):
                    build_external_query(source,bad)

    def test_wrong_candidate_is_sat_even_if_parser_accepts_it(self):
        if not shutil.which('z3'):
            self.skipTest('Z3 is installed on Python 3.13 CI')
        source=(OLD/'max2.sl').read_text()
        bad='(define-fun mux_2 ((x Int) (y Int)) Int x)'
        self.assertEqual(check_external_solution(source,bad).status,'counterexample')

    def test_real_cvc5_small_and_helper_function_benchmarks(self):
        # Prior cvc5 CI outputs; these cases are outside the original verifier.
        small=(NEW/'small.sl').read_text()
        small_solution='(define-fun f ((x Int) (y Int)) Int (ite (<= y x) x y))'
        helper=(NEW/'VC22_a.sl').read_text()
        helper_solution='(define-fun f ((x1 Int) (x2 Int)) Int (ite (= x1 x2) 0 1))'
        self.assertIn('(define-fun V_min', build_external_query(helper,helper_solution))
        self.assertIn('(define-fun f ',build_external_query(small,small_solution))
        if shutil.which('z3'):
            self.assertEqual(check_external_solution(small,small_solution).status,'proved')
            self.assertEqual(check_external_solution(helper,helper_solution).status,'proved')

    def test_multi_function_candidate_requires_all_definitions(self):
        source=(NEW/'VC22_b.sl').read_text()
        one='(define-fun f1 ((x1 Int) (x2 Int)) Int 0)'
        both=one+'\n(define-fun f2 ((x1 Int) (x2 Int)) Int 0)'
        with self.assertRaises(Unsupported):
            build_external_query(source,one)
        self.assertIn('(define-fun f2',build_external_query(source,both))

    def test_out_of_scope_width_still_externally_checked(self):
        source=(NEW/'max7.sl').read_text()
        vars=' '.join(f'(x{i} Int)' for i in range(1,8))
        bad=f'(define-fun max7 ({vars}) Int x1)'
        self.assertIn('(declare-const x7 Int)',build_external_query(source,bad))
        if shutil.which('z3'):
            self.assertEqual(check_external_solution(source,bad).status,'counterexample')


if __name__=='__main__':
    unittest.main()
