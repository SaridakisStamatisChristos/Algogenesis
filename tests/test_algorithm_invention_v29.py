"""v2.9: algorithm discovery is executable, reproducible, and falsifiable."""
import itertools
import random
import unittest

from algogenesis import bubble_network, run
from advanced import prefix_beam
from discovery import verify
from algorithm_invention_v29 import (
    matching_grammar, invent, flatten, dependency_depth,
    validate_stages, scalar_certificate,
)


class InventionTests(unittest.TestCase):
    def test_stage_grammar_contains_only_disjoint_pairs(self):
        for width in (2, 3, 5, 6):
            grammar = matching_grammar(width)
            self.assertEqual(len(grammar),len(set(grammar)))
            self.assertGreater(len(grammar),0)
            for stage in grammar:
                validate_stages((stage,),width)
                self.assertLessEqual(len(stage),width//2)
        self.assertEqual(len(matching_grammar(6)),75)

    def test_generates_size_and_depth_improvements_not_benchmark_solution_lookups(self):
        for width, size, depth, baseline_size, baseline_depth in (
                (5, 9, 5, 10, 7), (6, 12, 5, 15, 9)):
            with self.subTest(width=width):
                result = invent(width,max_stages=depth,
                                max_comparators=size,beam=256)
                self.assertEqual(result.status,'verified',result)
                self.assertEqual(len(result.stages),depth)
                net=flatten(result.stages)
                self.assertEqual(len(net),size)
                self.assertLess(len(net),len(bubble_network(width)))
                self.assertEqual(dependency_depth(net,width),depth)
                self.assertLess(depth,dependency_depth(bubble_network(width),width))
                self.assertTrue(verify(net,width)['verified'])
                self.assertTrue(scalar_certificate(result.stages,width)['valid'])
                report=result.report()
                self.assertEqual(report['candidate']['comparator_saving'],
                                 baseline_size-size)
                self.assertEqual(report['candidate']['depth_saving'],
                                 baseline_depth-depth)
                self.assertFalse(report['candidate']['global_optimality_proved'])
                self.assertFalse(report['candidate']['novel_algorithm_claim'])
                self.assertEqual(report['status'],'verified')
                self.assertEqual(len(report['candidate']['stages']),depth)
                self.assertEqual(len(report['best_errors']),depth+1)
                for permutation in itertools.permutations(range(width)):
                    self.assertEqual(run(net,permutation),list(range(width)))

    def test_real_gain_over_existing_width6_semantic_beam_depth(self):
        old=prefix_beam(6,12,beam=1024,seed=0)
        self.assertIsNotNone(old)
        new=invent(6,max_stages=5,max_comparators=12,beam=256)
        self.assertEqual(new.status,'verified')
        self.assertLessEqual(len(flatten(new.stages)),len(old))
        self.assertLess(dependency_depth(flatten(new.stages),6),
                        dependency_depth(old,6))

    def test_repeatability_and_large_negative_values(self):
        first=invent(6,beam=256)
        second=invent(6,beam=256)
        self.assertEqual(first,second)
        rng=random.Random(712)
        net=flatten(first.stages)
        for _ in range(500):
            vals=tuple(rng.randint(-10**12,10**12) for _ in range(6))
            self.assertEqual(run(net,vals),sorted(vals))

    def test_counterexamples_are_not_hidden(self):
        result=invent(6,beam=256)
        net=flatten(result.stages)
        self.assertFalse(verify(net[:-1],6)['verified'])
        shortened=result.stages[:-1] + (result.stages[-1][:-1],)
        if shortened[-1]:
            oracle=scalar_certificate(shortened,6)
            self.assertFalse(oracle['valid'])
            self.assertIsNotNone(oracle['first_counterexample'])
        for stages in (
                (((0,1),(1,2)),),
                (((0,6),),),
                (((2,1),),),
                (((),),),
                ((),),
        ):
            with self.subTest(stages=stages):
                with self.assertRaises(ValueError):
                    validate_stages(stages,6)

    def test_infeasible_bounds_and_budget_cannot_claim_discovery(self):
        insufficient=invent(6,max_stages=1,max_comparators=3,beam=256)
        self.assertEqual(insufficient.status,'not_found_in_bounds')
        self.assertIsNone(insufficient.stages)
        self.assertNotIn('candidate',insufficient.report())
        aborted=invent(6,max_stages=5,max_comparators=12,beam=256,
                       max_evaluations=1)
        self.assertEqual(aborted.status,'budget_exhausted')
        self.assertIsNone(aborted.stages)
        for kw in ({'width':9}, {'beam':0}, {'max_comparators':0},
                   {'max_stages':0}, {'max_evaluations':0}, {'width':True}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    invent(**kw)


if __name__=='__main__':
    unittest.main()
