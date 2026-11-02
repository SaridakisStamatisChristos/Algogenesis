"""Regression and adversarial validation of v3.1 structural genome evolution."""
from dataclasses import replace
import random
import unittest

from algorithm_genome_v30 import (
    Machine, Stmt, Genome, atom, integer, boolean, op, discover,
    type_check)
from genome_evolution_v31 import evolve, mutations, _case_sets, _matches


class GenomeEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.count = evolve('count')
        cls.contains = evolve('contains')
        cls.summation = evolve('sum')
        cls.clamp = evolve('clamp')

    def test_count_generates_conditional_branch_and_reduces_heldout_work(self):
        result = self.count
        self.assertEqual(result.result, 'empirically_validated')
        self.assertGreater(result.proposals, 0)
        self.assertGreater(result.valid, 0)
        self.assertTrue(any('predicate-increment-to-branch' in h['rule']
                            for h in result.history))
        self.assertNotEqual(result.genome, result.baseline)
        # Equal number of value comparisons: optimization is VM steps.
        self.assertEqual(result.baseline_heldout[0], result.evolved_heldout[0])
        self.assertEqual(result.evolved_heldout[1], 0)
        self.assertLess(result.evolved_heldout[2],
                        result.baseline_heldout[2] * .90)
        self.assertFalse(result.report()['global_optimality_claim'])
        self.assertFalse(result.report()['global_novelty_claim'])

    def test_heldout_fitness_mismatch_and_unsuccessful_tasks_preserved(self):
        self.assertLess(self.contains.evolved_fitness[0],
                        self.contains.baseline_fitness[0])
        self.assertEqual(self.contains.evolved_heldout[0],
                         self.contains.baseline_heldout[0])
        for result in (self.summation, self.clamp):
            self.assertEqual(result.result, 'no_fitness_improvement')
            self.assertEqual(result.evolved_heldout, result.baseline_heldout)
            self.assertEqual(result.genome, result.baseline)

    def test_determinism_and_serializable_trace(self):
        self.assertEqual(self.count, evolve('count'))
        self.assertEqual(self.count.heldout_cases, 51)
        import json
        report = self.count.report()
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertGreaterEqual(len(report['history']), 1)

    def test_mutation_family_covers_loops_branches_arrays_and_registers(self):
        count = discover('count').genome
        rules = [r for _,r in mutations(count)]
        self.assertTrue(any('predicate-increment-to-branch' in r for r in rules))
        contained = [r for _,r in mutations(discover('contains').genome)]
        self.assertTrue(any('reverse-loop' in r for r in contained))
        self.assertTrue(any('loop-stop-mutation' in r for r in contained))
        clamped = [r for _,r in mutations(discover('clamp').genome)]
        self.assertTrue(any('array-write-mutation' in r for r in clamped))
        self.assertTrue(any('invert-if' in r for r in clamped))
        for child,rule in mutations(count, cap=200):
            type_check(child)
            self.assertTrue(rule)
        self.assertEqual(len(list(mutations(count, cap=1))), 1)
        with self.assertRaises(ValueError):
            list(mutations(count, cap=0))

    def test_predicate_increment_rewrite_is_semantics_preserving(self):
        for truth in (False, True):
            original=Genome((('r','int',integer(3)),),
                            (Stmt('set', name='r', expr=op('add',atom('r'),
                                            op('btoi',boolean(truth)))),),
                            atom('r'),'int')
            rewritten=[g for g,rule in mutations(original)
                       if 'predicate-increment-to-branch' in rule]
            self.assertEqual(len(rewritten),1)
            for vals in ((),(0,),(1,2,3)):
                self.assertEqual(Machine().run(original,vals,0).value,
                                 Machine().run(rewritten[0],vals,0).value)
        wrong=Genome((('r','int',integer(3)),),
                     (Stmt('set',name='r',expr=op('add',atom('r'),integer(1))),),
                     atom('r'),'int')
        self.assertNotEqual(Machine().run(wrong,(),0).value,
                            Machine().run(Genome((('r','int',integer(3)),),
                               (Stmt('set',name='r',expr=op('add',atom('r'),
                                  op('btoi',boolean(False)))),),
                               atom('r'),'int'),(),0).value)

    def test_holdout_no_overlap_budget_rejection(self):
        train,validation,fitness,hold=_case_sets(1907)
        self.assertEqual(len(hold),51)
        self.assertFalse(set(hold)&(set(train)|set(validation)|set(fitness)))
        for kw in ({'beam':0},{'max_proposals':0},{'generations':0},
                   {'max_mutations':0},{'seed':True}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                evolve('count',**kw)
        with self.assertRaises(ValueError):
            evolve('not_a_task')

    def test_random_large_integer_differential_tests(self):
        rng = random.Random(31273)
        for task,result in [('count',self.count),('contains',self.contains),
                            ('sum',self.summation),('clamp',self.clamp)]:
            for n in (0,1,3,10,30,64,128):
                for _ in range(5):
                    values=tuple(rng.randrange(-10**12,10**12) for _ in range(n))
                    key=rng.choice(values) if values and rng.random()<.5 else 733
                    self.assertTrue(_matches(Machine(),result.genome,
                                             task,values,key))


if __name__=='__main__':
    unittest.main()
