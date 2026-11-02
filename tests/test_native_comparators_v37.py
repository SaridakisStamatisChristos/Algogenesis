"""Real native comparator correctness, provenance, and negative evidence."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from algorithm_genome_v30 import to_dict
from genome_headtail_v33 import discover_headtail
from native_autotune_v35 import EVAL_CELLS
from native_blinded_v36 import PROTOCOL as V36_PROTOCOL
from native_comparators_v37 import compare, source_for


class NativeCompetitorTests(unittest.TestCase):
    def fixture(self, path, task='count_max'):
        selected=to_dict(discover_headtail(task).genome)
        path.write_text(json.dumps({
            'protocol':V36_PROTOCOL,'task':task,
            'status':'blinded_native_experiment_complete',
            'selection_measurements_exclude_holdout_cells':True,
            'selected_index':0,'selected_genome':selected,
            'profiled_candidates':[{'index':0,'score':1.1,'genome':selected}]}))

    def test_invalid_provenance_and_budgets_fail_before_compilation(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact=Path(tmp)/'v36.json'
            self.fixture(artifact)
            for kwargs in ({'repetitions':True},{'repetitions':1},
                           {'elements_per_sample':9999},{'task':'sum_max'}):
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                    compare(kwargs.pop('task','count_max'),artifact,**kwargs)
            data=json.loads(artifact.read_text())
            data['selected_genome']={'forged':'program'}
            artifact.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                compare('count_max',artifact)

    @unittest.skipUnless(shutil.which('gcc'),'requires GCC')
    def test_four_task_oracles_and_raw_expanded_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            for task in ('count_max','count_min','sum_max','sum_min'):
                with self.subTest(task=task):
                    artifact=Path(tmp)/('v36_'+task+'.json')
                    self.fixture(artifact,task)
                    report=compare(task,artifact,repetitions=2,
                                   elements_per_sample=10000,output_dir=Path(tmp)/task)
                    self.assertEqual(report['native_verification'],'passed')
                    self.assertEqual(report['ubsan'],'passed')
                    self.assertEqual(report['raw_samples'],24)
                    self.assertEqual(report['summary']['cells_total'],12)
                    self.assertEqual({(c['length'],c['distribution']) for c in report['cells']},
                                     EVAL_CELLS)
                    self.assertIn('branchless_ns',report['native_baselines'])
                    self.assertEqual('avx2_ns' in report['native_baselines'],
                                     report['avx2_available'])
                    self.assertFalse(report['global_sota_claim'])
                    for suffix in ('c','csv','json'):
                        self.assertTrue((Path(tmp)/task/('v37_'+task+'.'+suffix)).exists())

    def test_source_includes_semantics_matched_reference_functions(self):
        genome=discover_headtail('sum_min').genome
        source=source_for(genome,'sum_min')
        for name in ('ag_generated','ag_ref_better','ag_ref_equal',
                     'ag_ref_branchless','ag_ref_avx2','ag_ref_two_pass'):
            self.assertIn(name,source)
        with self.assertRaises(ValueError):
            source_for(genome,'invalid')


if __name__=='__main__':
    unittest.main()
