"""Tests for bounded, honestly evaluated native-guided structural search."""
import shutil
import tempfile
import unittest
from pathlib import Path

from native_autotune_v35 import (
    TRAIN_CELLS, EVAL_CELLS, partition, score_selection, shortlist,
    valid_genomes, SearchConfig, autotune,
)
from genome_headtail_v33 import discover_headtail


class NativeAutotuneTests(unittest.TestCase):
    def test_exact_predeclared_holdout_split_and_no_score_leakage(self):
        self.assertEqual(len(TRAIN_CELLS),6)
        self.assertEqual(len(EVAL_CELLS),12)
        self.assertFalse(TRAIN_CELLS & EVAL_CELLS)
        cells=[{'length':n,'distribution':dist,
                'ratio_to_strong':(1.1 if (n,dist) in TRAIN_CELLS else 999.0)}
               for n,dist in sorted(TRAIN_CELLS | EVAL_CELLS)]
        selected,evals=partition(cells)
        self.assertEqual(set(selected),TRAIN_CELLS)
        self.assertEqual(set(evals),EVAL_CELLS)
        self.assertAlmostEqual(score_selection(selected),1.1)
        # Deliberately alter EVERY heldout value. The selection score
        # must remain exactly unchanged.
        for c in cells:
            if (c['length'],c['distribution']) in EVAL_CELLS:
                c['ratio_to_strong']=0.0001
        selection2,_=partition(cells)
        self.assertAlmostEqual(score_selection(selection2),1.1)
        with self.assertRaises(ValueError):
            score_selection(evals)

    def test_shortlist_keeps_baseline_and_fails_invalid_caps(self):
        pool=tuple(range(25))
        subset=shortlist(pool,8,6)
        self.assertEqual(len(subset),6)
        self.assertIn(8,subset)
        self.assertEqual(len(set(subset)),6)
        self.assertEqual(shortlist((1,2),1,6),(1,2))
        with self.assertRaises(AssertionError):
            shortlist(pool,100,6)
        for bad in (0,1,True,17):
            with self.assertRaises(ValueError):
                shortlist(pool,8,bad)

    def test_candidate_discovery_filters_by_independent_correctness(self):
        proposed,correct=valid_genomes('count_max')
        self.assertEqual(proposed,768)
        self.assertGreaterEqual(len(correct),2)
        self.assertIn(discover_headtail('count_max').genome,correct)
        self.assertEqual((proposed,correct),valid_genomes('count_max'))
        with self.assertRaises(ValueError):
            valid_genomes('not_a_task')

    def test_invalid_configuration_rejected_before_compilation(self):
        for settings in (SearchConfig(task='unknown'),
                         SearchConfig(max_profiles=1),
                         SearchConfig(max_profiles=17),
                         SearchConfig(training_repetitions=1),
                         SearchConfig(final_repetitions=0),
                         SearchConfig(training_elements=0),
                         SearchConfig(seed=True)):
            with self.subTest(settings=settings),self.assertRaises(ValueError):
                autotune(settings)

    @unittest.skipUnless(shutil.which('gcc'), 'requires GCC native C compiler')
    def test_real_native_tournament_and_all_losses_preserved(self):
        cfg=SearchConfig(task='count_max',max_profiles=2,
                         training_repetitions=2,training_elements=10000,
                         final_repetitions=2,final_elements=10000)
        with tempfile.TemporaryDirectory() as tmp:
            result=autotune(cfg,output_dir=tmp)
            self.assertEqual(result['status'],'native_experiment_complete')
            self.assertEqual(result['grammar_proposals'],768)
            self.assertEqual(result['native_profiled'],2)
            self.assertEqual(len(result['profiled_candidates']),2)
            self.assertEqual(result['heldout_selected']['cells_total'],12)
            self.assertEqual(result['heldout_v33']['cells_total'],12)
            self.assertIn(result['selected_index'],(0,1))
            self.assertFalse(result['global_sota_claim'])
            self.assertFalse(result['selected_on_heldout'])
            self.assertEqual(result['selected_native_result']['ubsan'],'passed')
            self.assertEqual(result['baseline_native_result']['ubsan'],'passed')
            for suffix in ('v35_count_max.json','v34_count_max.c',
                           'v34_count_max.csv','v34_count_max.json'):
                self.assertTrue((Path(tmp)/suffix).exists())


if __name__=='__main__':
    unittest.main()
