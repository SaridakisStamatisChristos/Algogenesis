"""Adversarial v2.7 tests for structural specification recognition."""
from pathlib import Path
import itertools
import random
import unittest

from structural_max import synthesize_structural_max
from sygus_clia import (parse_problem, Unsupported, certify, Affine, Tree,
                         synthesize, output, Result)
from sygus_smt_bridge import check_with_smt
import shutil

ROOT = Path(__file__).resolve().parent.parent
PINNED = ROOT / 'benchmarks' / 'sygus_clia_v27'


class StructuralMaxTests(unittest.TestCase):
    def test_max5_max6_exact_external_and_large_inputs(self):
        for n in (5,6):
            with self.subTest(n=n):
                source = (PINN / f'max{n}.sl').read_text(encoding='utf-8')
                problem = parse_problem(source)
                candidate = synthesize_structural_max(problem)
                self.assertIsNotNone(candidate)
                self.assertEqual(candidate.input_count,n)
                self.assertEqual(candidate.nodes,2**n-1)
                rng = random.Random(n*775)
                for _ in range(300):
                    values = tuple(rng.randrange(-10**9, 10**9) for _ in range(n))
                    self.assertEqual(candidate.tree.at(values), max(values))
                for v in (-5,0,5):
                    self.assertEqual(candidate.tree.at((v,)*n),v)
                with self.assertRaises(Unsupported):
                    certify(problem,candidate.tree)
                with self.assertRaises(ValueError):
                    synthesize(problem)
                if shutil.which('z3'):
                    rendered=output(problem,Result(candidate.tree,0,0,0,None,'candidate'))
                    self.assertEqual(check_with_smt(source,rendered,solver='z3').status,
                                     'proved')

    def test_all_zero_or_equal_and_nondeterministic_tree_not_assumed(self):
        source=(PINN/'max5.sl').read_text()
        problem=parse_problem(source)
        candidate=synthesize_structural_max(problem)
        self.assertEqual(candidate.tree.at((3,3,3,3,3)),3)
        self.assertEqual(candidate.tree.at((3,3,4,4,3)),4)

    def test_reject_constraint_mutations_and_partial_specification(self):
        source=(PINN/'max5.sl').read_text()
        original=parse_problem(source)
        self.assertIsNotNone(synthesize_structural_max(original))
        cases=[
            source.replace('(>= (max5 x y z w u) u)', '(<= (max5 x y z w u) u)'),
            source.replace('(>= (max5 x y z w u) u)', '(>= (max5 x y z w u) w)'),
            source.replace('(>= (max5 x y z w u) u)', '(>= (max5 x y z w u) (+ u 1))'),
            source.replace('(check-synth)', '(constraint (>= (max5 x y z w u) 100))\n(check-synth)'),
            source.replace('(or (= u (max5 x y z w u))', '(or (= x (max5 x y z w u))'),
        ]
        for idx,case in enumerate(cases):
            with self.subTest(case=idx):
                self.assertIsNone(synthesize_structural_max(parse_problem(case)))

    def test_reject_unsupported_arity_and_non_max_contracts(self):
        for name in ('small.sl',):
            problem = parse_problem((PINN/name).read_text())
            self.assertIsNone(synthesize_structural_max(problem))
        for name in ('max7.sl','max8.sl'):
            with self.assertRaises(Unsupported):
                parse_problem((PINN/name).read_text())

    def test_incorrect_max_candidate_has_real_smt_counterexample(self):
        if not shutil.which('z3'):
            self.skipTest('Z3 required for counterexample')
        source=(PINN/'max5.sl').read_text()
        bad='(define-fun max5 ((x Int) (y Int) (z Int) (w Int) (u Int)) Int x)'
        result=check_with_smt(source,bad,solver='z3')
        self.assertEqual(result.status,'counterexample',result)


if __name__ == '__main__':
    unittest.main()
