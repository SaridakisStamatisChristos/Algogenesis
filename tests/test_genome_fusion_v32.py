"""Independent adversarial tests for v3.2 synthesized loop fusion."""
import random
import unittest
from dataclasses import replace
from algorithm_genome_v30 import Machine, integer
from genome_fusion_v32 import fuse
from genome_crossover_v32 import _task_oracle, _cases


class FusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results={task:fuse(task) for task in
                     ('count_max','count_min','sum_max','sum_min')}

    def test_four_one_pass_correct_and_measurable_improvements(self):
        for task,result in self.results.items():
            with self.subTest(task=task):
                self.assertEqual(result.status,'empirically_validated')
                self.assertEqual(result.proposals,4)
                self.assertGreater(result.correct,0)
                self.assertEqual(len(result.genome.statements),1)
                self.assertEqual(len(result.genome.registers),2)
                self.assertLess(result.fused_heldout[0],result.baseline_heldout[0])
                self.assertLess(result.fused_heldout[1],result.baseline_heldout[1])
                self.assertEqual(result.fused_heldout[2],0)
                self.assertGreater(result.fused_heldout[0],
                                   result.strong_reference_comparisons)
                self.assertFalse(result.report()['sota_claim'])
                self.assertFalse(result.report()['universal_correctness_proved'])

    def test_differential_oracle_on_extreme_and_repeated_data(self):
        rng=random.Random(320320)
        for task,result in self.results.items():
            vm=Machine()
            for length in (0,1,2,4,16,64,128):
                for _ in range(15):
                    values=tuple(rng.randint(-10**25,10**25) for _ in range(length))
                    if length>0 and rng.random()<.25:
                        values=(values[0],)*length
                    output=vm.run(result.genome,values,0)
                    self.assertEqual(output.value,_task_oracle(task,values))
                    self.assertEqual(output.final_array,values)
                    self.assertEqual(output.writes,0)

    def test_bad_reset_mutation_is_falsified(self):
        good=self.results['count_max'].genome
        loop=good.statements[0]
        conditional=loop.then[0]
        wrong=replace(conditional,then=conditional.then[:-1]+(
            replace(conditional.then[-1],expr=integer(0)),))
        mutated=replace(good,statements=(replace(loop,then=(wrong,)),))
        self.assertNotEqual(Machine().run(mutated,(4,4),0).value,
                            _task_oracle('count_max',(4,4)))

    def test_reproducibility_no_holdout_leak_and_invalid_task(self):
        self.assertEqual(fuse('count_max'),self.results['count_max'])
        *_,heldout=_cases(3201)
        self.assertEqual(len(heldout),51)
        with self.assertRaises(ValueError):
            fuse('unsupported')


if __name__=='__main__':
    unittest.main()
