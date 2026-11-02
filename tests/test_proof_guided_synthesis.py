"""V2.8 black-box synthesis, budget and falsification tests."""
import shutil
from pathlib import Path
from unittest.mock import patch
import unittest

from sygus_clia import Unsupported
from sygus_smt_bridge import SMTCheck
from proof_guided_synthesis import (_form_candidates, _candidate_sources,
                                    _signatures, synthesize_verified)
from sygus_general_checker import check_external_solution

ROOT=Path(__file__).resolve().parent.parent
FIXTURES=ROOT/'benchmarks'/'sygus_clia_v27'


class ProofGuidedTests(unittest.TestCase):
    def test_enumerates_generic_grammar_without_task_names(self):
        forms=list(_form_candidates(('a','b')))
        self.assertIn('(ite (= a b) 0 1)',forms)
        self.assertIn('(ite (< a b) b a)',forms)
        self.assertIn('(- b a)',forms)
        self.assertEqual(len(forms),len(set(forms)))
        source='(set-logic LIA) (synth-fun f ((a Int) (b Int)) Int) '\
               '(declare-var a Int) (declare-var b Int) '\
               '(constraint (>= (f a b) a)) (check-synth)'
        sigs=_signatures(source)
        self.assertEqual(sigs,(('f',('a','b')),))
        self.assertTrue(next(_candidate_sources(sigs)).startswith('(define-fun f'))

    def test_multi_target_enumeration_is_joint(self):
        source=(FIXTURES/'VC22_b.sl').read_text()
        sigs=_signatures(source)
        self.assertEqual(len(sigs),2)
        emitted=list(_candidate_sources(sigs))
        self.assertGreater(len(emitted),100)
        self.assertIn('(define-fun f1',emitted[0])
        self.assertIn('(define-fun f2',emitted[0])
        self.assertTrue(any('(< x1 x2)' in term for term in emitted))
        self.assertTrue(any('(ite (= x1 x2) 0 1)' in term for term in emitted))

    def test_budget_failure_must_not_be_proved(self):
        source=(FIXTURES/'small.sl').read_text()
        with patch('proof_guided_synthesis.shutil.which',return_value='/usr/bin/z3'),\
             patch('proof_guided_synthesis.check_external_solution') as checker:
            checker.return_value=SMTCheck('counterexample','z3',0,'SAT')
            result=synthesize_verified(source,max_candidates=1)
            self.assertEqual(result.status,'budget_exhausted')
            self.assertIsNone(result.solution)
            self.assertEqual(result.checked,1)
            checker.return_value=SMTCheck('unknown','z3',0,'UNKNOWN')
            result=synthesize_verified(source,max_candidates=1)
            self.assertNotEqual(result.status,'proved')
            self.assertIsNone(result.solution)

    def test_missing_solver_and_input_validation(self):
        source=(FIXTURES/'small.sl').read_text()
        with patch('proof_guided_synthesis.shutil.which',return_value=None):
            self.assertEqual(synthesize_verified(source).status,'unavailable')
        for bad in (0,-1,True):
            with self.assertRaises(ValueError):
                synthesize_verified(source,max_candidates=bad)
        for bad in (
            source+'(assert false)',
            source.replace('(synth-fun f ((x Int) (y Int)) Int)',
                           '(synth-fun f ((x Int) (y Int)) Int ((Start Int (x))))')
        ):
            if bad==source:
                self.fail('mutation did not modify test source')
            with self.assertRaises(Unsupported):
                # The robust external validator, not the syntax-only
                # signature extractor, rejects arbitrary source commands.
                from sygus_general_checker import build_external_query
                definition='(define-fun f ((x Int) (y Int)) Int x)'
                build_external_query(bad,definition)

    @unittest.skipUnless(shutil.which('z3'),'external Z3 required')
    def test_official_underconstrained_small_is_proved(self):
        source=(FIXTURES/'small.sl').read_text()
        result=synthesize_verified(source,max_candidates=160,max_wall_seconds=5)
        self.assertEqual(result.status,'proved',result)
        self.assertIsNotNone(result.solution)
        self.assertEqual(check_external_solution(source,result.solution).status,'proved')

    @unittest.skipUnless(shutil.which('z3'),'external Z3 required')
    def test_official_helper_function_vc22_a_is_proved(self):
        source=(FIXTURES/'VC22_a.sl').read_text()
        result=synthesize_verified(source,max_candidates=160,max_wall_seconds=5)
        self.assertEqual(result.status,'proved',result)
        self.assertEqual(check_external_solution(source,result.solution).status,'proved')

    @unittest.skipUnless(shutil.which('z3'),'external Z3 required')
    def test_multi_target_search_never_claims_proof_without_z3(self):
        source=(FIXTURES/'VC22_b.sl').read_text()
        result=synthesize_verified(source,max_candidates=160,max_wall_seconds=5)
        if result.status=='proved':
            self.assertEqual(check_external_solution(source,result.solution).status,'proved')
        else:
            self.assertIsNone(result.solution)
            self.assertIn(result.status,('not_found_in_grammar','unverified','budget_exhausted'))


if __name__=='__main__':
    unittest.main()
