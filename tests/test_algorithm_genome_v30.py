"""v3.0 typed genome: independent oracles, adversarial falsification, resource limits."""
from dataclasses import replace
import json
import random
import unittest

from algorithm_genome_v30 import (
    Expr, Stmt, Genome, Machine, atom, integer, boolean, op,
    type_check, InvalidGenome, FuelExhausted, discover, oracle,
    all_training_cases, to_dict,
)


class TypedGenomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {task: discover(task) for task in
                       ('contains', 'count', 'sum', 'clamp')}

    def test_four_separate_algorithm_tasks_generated(self):
        for task, result in self.results.items():
            with self.subTest(task=task):
                self.assertEqual(result.status, 'empirically_validated')
                self.assertIsNotNone(result.genome)
                self.assertGreater(result.generated, 100)
                self.assertGreater(result.correct, 0)
                self.assertEqual(result.heldout, 51)
                self.assertIsInstance(to_dict(result.genome), dict)
                self.assertEqual(result.genome.output_type,
                                 'bool' if task == 'contains' else 'int')
                self.assertEqual(json.loads(json.dumps(result.report()))['status'],
                                 'empirically_validated')

    def test_membership_improves_comparisons_without_seeded_solution(self):
        result = self.results['contains']
        self.assertLess(result.mean_comparisons, result.baseline_mean_comparisons)
        self.assertLess(result.mean_comparisons / result.baseline_mean_comparisons, 0.80)
        self.assertTrue(any(stmt.stop_if is not None for stmt in result.genome.statements))

    def test_array_mutator_improves_writes_but_pays_extra_comparisons(self):
        result = self.results['clamp']
        self.assertLess(result.mean_writes, result.baseline_mean_writes)
        self.assertGreater(result.mean_comparisons, result.baseline_mean_comparisons)
        self.assertEqual(Machine().run(result.genome, (-4, 0, 5, -2), 1).final_array,
                         (0, 0, 5, 0))

    def test_count_and_sum_do_not_report_illusory_speedups(self):
        count = self.results['count']
        self.assertEqual(count.mean_comparisons, count.baseline_mean_comparisons)
        summation = self.results['sum']
        self.assertEqual(summation.mean_comparisons, 0.0)
        self.assertEqual(summation.baseline_mean_comparisons, 0.0)

    def test_training_exhaustiveness_plus_separate_large_heldouts(self):
        vm = Machine()
        rng = random.Random(63001)
        extended = [(tuple(rng.randint(-100, 100) for _ in range(n)),
                     rng.randint(-100, 100))
                    for n in (0, 1, 2, 3, 9, 31, 72, 128) for _ in range(8)]
        extended += [(tuple(range(n)), n + 3) for n in (0, 1, 5, 60, 128)]
        cases = (*all_training_cases(), *extended)
        for task, result in self.results.items():
            for values, key in cases:
                with self.subTest(task=task, n=len(values), key=key):
                    execution = vm.run(result.genome, values, key)
                    if task == 'clamp':
                        self.assertEqual(execution.final_array, oracle(task, values, key))
                    else:
                        self.assertEqual(execution.value, oracle(task, values, key))
                        self.assertEqual(execution.final_array, values)
                        self.assertEqual(execution.writes, 0)

    def test_mutation_falsifies_bad_early_break(self):
        genome = self.results['contains'].genome
        loop = genome.statements[0]
        self.assertIsNotNone(loop.stop_if)
        mutated = replace(genome, statements=(replace(loop, stop_if=boolean(True)),))
        self.assertFalse(Machine().run(mutated, (0, 0, 0, 7), 7).value)
        self.assertTrue(oracle('contains', (0, 0, 0, 7), 7))

    def test_real_branch_array_write_read_and_swap(self):
        cond = op('lt', atom('item'), integer(0))
        body = Stmt('if', cond=cond,
                    then=(Stmt('store', expr=atom('index'), other=integer(0)),))
        genome = Genome((('acc', 'int', integer(0)),),
                        (Stmt('foreach', then=(body,)),),
                        Expr('read', (integer(0),)), 'int')
        type_check(genome)
        output = Machine().run(genome, (-8, 3, -2), 123)
        self.assertEqual((output.value, output.final_array, output.writes),
                         (0, (0, 3, 0), 2))
        swapped = Genome((),
                         (Stmt('swap', expr=integer(0), other=integer(1)),),
                         Expr('read', (integer(0),)), 'int')
        self.assertEqual(Machine().run(swapped, (3, 8), 0).final_array, (8, 3))

    def test_static_type_errors_are_rejected(self):
        wrong = (
            Genome((('acc', 'bool', integer(0)),), (), boolean(False), 'bool'),
            Genome((('acc', 'int', integer(0)),),
                   (Stmt('set', name='acc', expr=boolean(False)),), atom('acc'), 'int'),
            Genome((), (Stmt('if', cond=integer(1)),), integer(0), 'int'),
            Genome((), (Stmt('foreach', then=(Stmt('foreach',
                   then=(Stmt('store', expr=integer(0), other=integer(1)),)),)),),
                   integer(0), 'int'),
            Genome((), (Stmt('store', expr=boolean(True), other=integer(0)),),
                   integer(0), 'int'),
            Genome((), (Stmt('unknown'),), integer(0), 'int'),
            Genome((), (), atom('ghost'), 'int'),
            Genome((), (), op('add', boolean(True), integer(1)), 'int'),
            Genome((), (), boolean(True), 'int'),
        )
        for genome in wrong:
            with self.subTest(genome=genome), self.assertRaises(InvalidGenome):
                type_check(genome)

    def test_resource_bounds_and_adversarial_array_access(self):
        genome = self.results['count'].genome
        with self.assertRaises(FuelExhausted):
            Machine(fuel=3).run(genome, (1, 2, 3, 4), 1)
        with self.assertRaises(ValueError):
            Machine(max_array=1).run(genome, (1, 2), 1)
        with self.assertRaises(ValueError):
            Machine().run(genome, (1, True), 1)
        with self.assertRaises(ValueError):
            Machine().run(genome, (1, 2), True)
        out_of_range = Genome((), (), Expr('read', (integer(99),)), 'int')
        with self.assertRaises(IndexError):
            Machine().run(out_of_range, (1, 2), 0)
        bad_write = Genome((), (Stmt('store', expr=integer(-1),
                                    other=integer(1)),), integer(0), 'int')
        with self.assertRaises(IndexError):
            Machine().run(bad_write, (1, 2), 0)

    def test_search_budget_and_repeatability(self):
        for task in ('contains', 'count', 'sum', 'clamp'):
            with self.subTest(task=task):
                self.assertEqual(discover(task, limit=1).status, 'not_found_in_bounds')
                self.assertEqual(discover(task), self.results[task])
        for opts in ({'limit': 0}, {'limit': True}, {'seed': True}):
            with self.assertRaises(ValueError):
                discover('contains', **opts)
        with self.assertRaises(ValueError):
            discover('unknown')


if __name__ == '__main__':
    unittest.main()
