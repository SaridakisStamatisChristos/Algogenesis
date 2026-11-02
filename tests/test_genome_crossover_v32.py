"""Adversarial proof-obligation tests for v3.2 multi-pass composition."""
import json
import random
import unittest
from dataclasses import replace
from algorithm_genome_v30 import (Genome, Machine, Stmt, atom, integer, op,
                                  type_check, InvalidGenome, discover)
from genome_evolution_v31 import evolve
from genome_crossover_v32 import (crossover, rename_expr, rename_stmt,
    discover_prefix, discover_composition, _task_oracle, _cases,
    _independent_one_pass_reference, _dominates)


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {t: discover_composition(t)
                       for t in ('count_max', 'count_min', 'sum_max', 'sum_min')}

    def test_four_independently_verified_two_pass_algorithms(self):
        for task, result in self.results.items():
            with self.subTest(task=task):
                self.assertEqual(result.status, 'empirically_validated')
                self.assertEqual(result.heldout_cases, 51)
                self.assertGreater(result.prefix_candidates, 100)
                self.assertGreater(result.verified_prefixes, 0)
                self.assertGreater(result.accepted_compositions, 0)
                self.assertGreater(result.pareto_points, 0)
                self.assertEqual(len(result.genome.statements), 2)
                self.assertEqual(len(result.genome.registers), 2)
                self.assertFalse(result.report()['universal_correctness_proved'])
                self.assertFalse(result.report()['novel_algorithm_claim'])
                self.assertFalse(result.report()['global_sota_claim'])
                self.assertEqual(json.loads(json.dumps(result.report()))['task'], task)
                type_check(result.genome)

    def test_random_and_adversarial_signed_integer_arrays(self):
        rng = random.Random(83991)
        vm = Machine()
        for task, result in self.results.items():
            for n in (0, 1, 2, 3, 4, 16, 32, 64, 128):
                for _ in range(20):
                    values = tuple(rng.randrange(-10**37, 10**37) for _ in range(n))
                    if n and rng.randrange(3) == 0:
                        values = (values[0],) * n
                    actual = vm.run(result.genome, values, -999)
                    self.assertEqual(actual.value, _task_oracle(task, values))
                    self.assertEqual(actual.final_array, values)
                    self.assertEqual(actual.writes, 0)
            for values in ((), (-10**100,), (-10**100,) * 128,
                           (10**100,) * 128, (-9, 3, -9, 3, -9),
                           tuple(range(-64, 64)), tuple(range(64, -64, -1))):
                self.assertEqual(vm.run(result.genome, values, 0).value,
                                 _task_oracle(task, values))

    def test_prefix_synthesized_from_grammar_not_lookup(self):
        vm = Machine()
        for mode in ('max', 'min'):
            prefix, proposed, verified = discover_prefix(mode)
            self.assertEqual(proposed, 408)
            self.assertGreater(verified, 0)
            self.assertEqual(len(prefix.statements), 1)
            self.assertEqual(prefix.result, atom('best'))
            for values in ((), (-12,), (-100, -200), (-200, -100),
                           (-2, 0, 1, 44, -100), tuple(range(60, -60, -1))):
                expectation = (max(values) if mode == 'max' else min(values)) if values else 0
                self.assertEqual(vm.run(prefix, values, 0).value, expectation)
        with self.assertRaises(ValueError):
            discover_prefix('invalid')

    def test_grafted_parents_are_generated_separately(self):
        prefix = discover_prefix('max')[0]
        for parent in (discover('count').genome, evolve('count').genome):
            joint = crossover(prefix, parent, renames={'acc':'frequency', 'key':'best'})
            type_check(joint)
            self.assertEqual(tuple(x[0] for x in joint.registers), ('best', 'frequency'))
            self.assertEqual(joint.result, atom('frequency'))
            self.assertEqual(joint.statements[0], prefix.statements[0])
            self.assertNotEqual(joint.statements[1], parent.statements[0])
            for values in ((), (1, 1, 2), (100, 50, -100), (2,) * 100):
                self.assertEqual(Machine().run(joint, values, 333).value,
                                 _task_oracle('count_max', values))

    def test_colliding_registers_and_bad_semantics_are_rejected(self):
        prefix = discover_prefix('max')[0]
        parent = discover('count').genome
        for bad in ({'acc':'best'}, {'acc':'item'}, {'acc':True}, []):
            with self.subTest(bad=bad), self.assertRaises(InvalidGenome):
                crossover(prefix, parent, renames=bad)
        result = self.results['count_max']
        broken = replace(result.genome, statements=result.genome.statements[1:])
        self.assertNotEqual(Machine().run(broken, (1,2,2), 0).value,
                            _task_oracle('count_max', (1,2,2)))
        self.assertNotEqual(Machine().run(self.results['count_min'].genome,
                                         (0,1,1), 0).value,
                            _task_oracle('count_max', (0,1,1)))

    def test_alpha_renaming_reaches_nested_predicates_and_array_operations(self):
        branch = Stmt('if', cond=op('eq',atom('key'),integer(1)),
                      then=(Stmt('store',expr=atom('index'),other=atom('key')),),
                      otherwise=(Stmt('set',name='acc',expr=atom('key')),))
        renamed = rename_stmt(branch, {'acc':'score','key':'best'})
        self.assertEqual(renamed.cond.args[0],atom('best'))
        self.assertEqual(renamed.then[0].other,atom('best'))
        self.assertEqual(renamed.otherwise[0].name,'score')
        self.assertEqual(renamed.otherwise[0].expr,atom('best'))
        self.assertEqual(rename_expr(atom('irrelevant'),{'key':'best'}),atom('irrelevant'))

    def test_disjoint_evaluation_and_strong_one_pass_comparator(self):
        train, validation, fitness, heldout = _cases(3201)
        self.assertEqual(len(heldout), 51)
        self.assertFalse(set(heldout) & (set(train)|set(validation)|set(fitness)))
        self.assertEqual(_cases(3201),_cases(3201))
        self.assertNotEqual(_cases(3201)[-1],_cases(3202)[-1])
        for task, result in self.results.items():
            # Explicitly record that two-pass results are slower on comparison count
            # than the separately correct one-pass implementation: NO SOTA claim.
            self.assertGreater(result.heldout[0],result.scalar_reference_comparisons)
            self.assertAlmostEqual(result.scalar_reference_comparisons,
                                   _independent_one_pass_reference(task,heldout))
        self.assertTrue(_dominates((1,2,3),(2,2,3)))
        self.assertFalse(_dominates((2,2,3),(1,2,3)))
        self.assertFalse(_dominates((2,2,3),(2,2,3)))

    def test_determinism_and_invalid_inputs(self):
        self.assertEqual(self.results['count_max'],discover_composition('count_max'))
        for task in ('invalid','count','max'):
            with self.assertRaises(ValueError):
                discover_composition(task)
        with self.assertRaises(ValueError):
            discover_composition('count_max',seed=True)


if __name__=='__main__':
    unittest.main()
