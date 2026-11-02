"""Reproducibility and outcome-classification tests for v2.7 harness."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from benchmark_v27 import (_blob_sha,_candidate_from_output,_run_subprocess,
                           _record_status,DEFAULT_MANIFEST,ROOT)


class BenchmarkV27Tests(unittest.TestCase):
    def test_frozen_manifest_source_blobs(self):
        doc=json.loads(DEFAULT_MANIFEST.read_text(encoding='utf-8'))
        self.assertEqual(doc['source_commit'],
                         '13c8deb68a873635879c9a69bc78caebd340f646')
        self.assertEqual(len(doc['benchmarks']),12)
        self.assertEqual(len({x['name'] for x in doc['benchmarks']}),12)
        for item in doc['benchmarks']:
            with self.subTest(item=item['name']):
                path=(ROOT/item['file']).resolve()
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertEqual(_blob_sha(path.read_bytes()),item['git_blob_sha'])

    def test_benchmark_candidate_extracts_one_definition_only(self):
        example='(define-fun f ((x Int)) Int (ite (> x 0) x 0))'
        self.assertEqual(_candidate_from_output(example),example)
        self.assertEqual(_candidate_from_output('('+example+')'),example)
        for text in ('sat','unsat','unknown','(error "unsupported")',
                     '(define-fun f ((x Int)) Int x) (exit)',
                     '(define-fun f ((x Int)) Int x', ''):
            with self.subTest(output=text):
                self.assertIsNone(_candidate_from_output(text))

    def test_subprocess_timeout_and_unavailable_are_not_proof(self):
        with patch('benchmark_v27.subprocess.run') as run:
            run.side_effect=subprocess.TimeoutExpired(['x'],1)
            self.assertEqual(_run_subprocess(['x'],1)['status'],'timeout')
            run.side_effect=FileNotFoundError()
            self.assertEqual(_run_subprocess(['x'],1)['status'],'unavailable')
            run.side_effect=None
            run.return_value=subprocess.CompletedProcess([],1,'','bad')
            self.assertEqual(_run_subprocess(['x'],1)['status'],'error')
            run.return_value=subprocess.CompletedProcess([],0,'unsat','')
            self.assertEqual(_run_subprocess(['x'],1)['status'],'candidate')
        self.assertNotEqual(_record_status('unverified',1)['status'],'proved')


if __name__=='__main__':
    unittest.main()
