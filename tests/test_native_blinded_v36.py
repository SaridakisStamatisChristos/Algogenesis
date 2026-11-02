"""Selection isolation and native provenance gates for the v3.6 experiment."""
import shutil
import tempfile
import unittest
from pathlib import Path

from genome_headtail_v33 import discover_headtail
from native_autotune_v35 import TRAIN_CELLS, EVAL_CELLS
from native_benchmark_v34 import run_benchmark
from native_blinded_v36 import Config, HOLDOUT_SEED, SELECTION_SEED, run


class BlindedExperimentTests(unittest.TestCase):
    def test_heldout_measurements_begin_only_after_selection_is_frozen(self):
        calls=[]
        def fake_benchmark(task, *, genome_json, cells, data_seed, **kwargs):
            calls.append((frozenset(cells),data_seed,Path(genome_json).name))
            ratio=1.0 if data_seed==SELECTION_SEED else 999.0
            return {'cells':[{'length':n,'distribution':d,
                              'ratio_to_strong':ratio,
                              'median_ns_per_call':{'generated_ns':ratio}}
                             for n,d in sorted(cells)],
                    'requested_cells':[list(c) for c in sorted(cells)],
                    'data_seed':data_seed}
        config=Config(max_profiles=2)
        result=run(config,benchmark=fake_benchmark)
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[:2],[(TRAIN_CELLS,SELECTION_SEED,'candidate_0.json'),
                                    (TRAIN_CELLS,SELECTION_SEED,'candidate_1.json')])
        self.assertEqual(calls[2:],[(EVAL_CELLS,HOLDOUT_SEED,'winner.json'),
                                    (EVAL_CELLS,HOLDOUT_SEED,'baseline.json')])
        self.assertEqual(result['selection_score'],1.0)
        self.assertAlmostEqual(result['holdout_selected']['geometric_ratio_to_strong'],999.0)
        self.assertFalse(result['global_sota_claim'])

    def test_invalid_partitions_and_seeds_fail_closed(self):
        for cells in (set(),{(16,'unknown')},[next(iter(TRAIN_CELLS))]):
            with self.subTest(cells=cells),self.assertRaises(ValueError):
                run_benchmark(cells=cells)
        for seed in (True,0,-1,1<<64):
            with self.subTest(seed=seed),self.assertRaises(ValueError):
                run_benchmark(data_seed=seed)

    @unittest.skipUnless(shutil.which('gcc'),'requires GCC')
    def test_real_native_runner_emits_only_requested_cells(self):
        from algorithm_genome_v30 import to_dict
        import json
        with tempfile.TemporaryDirectory() as temp:
            artifact=Path(temp)/'candidate.json'
            artifact.write_text(json.dumps({'task':'count_max',
                'candidate':to_dict(discover_headtail('count_max').genome)}))
            result=run_benchmark('count_max',genome_json=artifact,
                                 cells=TRAIN_CELLS,data_seed=SELECTION_SEED,
                                 repetitions=2,elements_per_sample=10000)
            self.assertEqual(result['raw_samples'],12)
            self.assertEqual({(c['length'],c['distribution']) for c in result['cells']},
                             TRAIN_CELLS)
            self.assertEqual(result['ubsan'],'passed')


if __name__=='__main__':
    unittest.main()
