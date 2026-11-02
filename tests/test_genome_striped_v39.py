"""Two-lane summary invariants, structural search and native execution."""
from dataclasses import replace
from itertools import product
import shutil
import tempfile
import unittest
from pathlib import Path

from algorithm_genome_v30 import Genome, Machine, atom, integer, op, type_check, InvalidGenome
from genome_crossover_v32 import _task_oracle
from genome_headtail_v33 import candidates as old_candidates
from genome_select_v38 import candidates as select_candidates
from genome_striped_v39 import candidates, discover, experiment


class StripedGenomeTests(unittest.TestCase):
    def test_bitwise_index_expression_is_typed(self):
        parity=op('band',integer(3),integer(1))
        program=Genome((),(),parity,'int')
        type_check(program)
        self.assertEqual(Machine().run(program,(),0).value,1)
        with self.assertRaises(InvalidGenome):
            type_check(Genome((),(),op('band',integer(1),atom('missing')),'int'))

    def test_search_has_new_partial_summary_structure(self):
        proposed=list(candidates())
        self.assertEqual(len(proposed),1536)
        old=set(old_candidates())|set(select_candidates())
        self.assertFalse(any(g in old for g in proposed))
        for g in proposed:
            self.assertEqual(len(g.registers),4)
            self.assertEqual(g.statements[2].op,'foreach')
            self.assertEqual(g.statements[2].then[0].cond.args[0].op,'band')
        for task,expected in (('count_max',8),('count_min',8),
                              ('sum_max',32),('sum_min',32)):
            with self.subTest(task=task):
                result=discover(task)
                self.assertEqual((result.proposed,result.correct),(1536,expected))
                self.assertEqual(result.python_holdout_cases,51)
                self.assertNotIn(result.genome,old)

    def test_lane_invariants_on_exhaustive_small_arrays(self):
        vm=Machine()
        for task in ('count_max','sum_min'):
            genome=discover(task).genome
            probes={name:replace(genome,result=atom(name))
                    for name in ('best0','best1','frequency0','frequency1')}
            for n in range(6):
                for values in product((-2,0,2),repeat=n):
                    with self.subTest(task=task,values=values):
                        self.assertEqual(vm.run(genome,values,0).value,
                                         _task_oracle(task,values))
                        for lane in (0,1):
                            subset=values[lane::2]
                            best=(max(subset) if task.endswith('max') else min(subset)) if subset else 0
                            if subset:
                                self.assertEqual(vm.run(probes['best'+str(lane)],values,0).value,
                                                 best)
                            self.assertEqual(vm.run(probes['frequency'+str(lane)],values,0).value,
                                             _task_oracle(task,subset))

    @unittest.skipUnless(shutil.which('gcc'),'requires GCC')
    def test_real_generated_native_program_and_ubsan(self):
        with tempfile.TemporaryDirectory() as tmp:
            report=experiment('count_max',repetitions=2,
                              elements_per_sample=10000,output_dir=tmp)
            self.assertEqual(report['status'],'striped_genome_generated')
            self.assertEqual(report['grammar_proposals'],1536)
            self.assertEqual(report['finite_verified_genomes'],8)
            self.assertEqual(report['native_result']['ubsan'],'passed')
            self.assertEqual(report['native_summary']['cells_total'],12)
            self.assertFalse(report['global_novelty_claim'])
            self.assertTrue((Path(tmp)/'v39_count_max.json').exists())
            self.assertTrue((Path(tmp)/'v34_count_max.c').exists())


if __name__=='__main__':
    unittest.main()
