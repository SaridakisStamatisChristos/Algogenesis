"""Adversarial native code-generation and benchmark tests for v3.4."""
import ctypes
from dataclasses import replace
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from algorithm_genome_v30 import (Expr, Stmt, Genome, Machine, atom, integer,
                                  boolean, op, to_dict, type_check)
from genome_headtail_v33 import discover_headtail
from genome_crossover_v32 import _task_oracle
from native_codegen_v34 import compile_genome, decode_genome, UnsupportedNativeGenome
from native_benchmark_v34 import native_source, run_benchmark, TASKS


class NativeV34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.programs={task:discover_headtail(task).genome for task in TASKS}

    def test_json_roundtrip_typechecking_and_source_reproducibility(self):
        for task,g in self.programs.items():
            with self.subTest(task=task):
                parsed=decode_genome(json.loads(json.dumps(to_dict(g))))
                self.assertEqual(parsed,g)
                self.assertEqual(compile_genome(parsed),compile_genome(g))
                self.assertIn('AG_NOINLINE int64_t ag_generated',compile_genome(g))
                self.assertIn('ag_ref_better',native_source(g,task))
                self.assertIn('ag_ref_equal',native_source(g,task))
                self.assertIn('ag_ref_two_pass',native_source(g,task))

    def test_fail_closed_unsupported_code_and_type_mismatches(self):
        for genome in (
            Genome((),(Stmt('store',expr=integer(0),other=integer(1)),),
                   integer(0),'int'),
            Genome((),(Stmt('swap',expr=integer(0),other=integer(1)),),
                   integer(0),'int'),
            Genome((),(),boolean(True),'bool'),
            Genome((),(),integer(1<<70),'int'),
        ):
            with self.subTest(genome=genome),self.assertRaises(UnsupportedNativeGenome):
                compile_genome(genome)
        example=to_dict(self.programs['count_max'])
        example['forged']='drop table'
        with self.assertRaises(UnsupportedNativeGenome):
            decode_genome(example)
        example=to_dict(self.programs['count_max'])
        example['registers'][0][0]='__evil;'
        with self.assertRaises(UnsupportedNativeGenome):
            compile_genome(decode_genome(example))
        with self.assertRaises(ValueError):
            native_source(self.programs['count_max'],'unsupported')

    def test_vm_reverse_loop_start_semantics_no_regression(self):
        p=Genome((('total','int',integer(0)),),
                 (Stmt('foreach',start=1,reverse=True,
                       then=(Stmt('set',name='total',expr=op('add',atom('total'),atom('item'))),)),),
                 atom('total'),'int')
        type_check(p)
        for values in ((),(1,),(1,2,3,4),(-2,-3,7,5)):
            self.assertEqual(Machine().run(p,values,0).value,sum(values[1:]))
        self.assertIn('loop_1-- > 1;',compile_genome(p))

    @unittest.skipUnless(shutil.which('gcc'), 'C compiler not available locally')
    def test_native_functions_match_independent_python_oracle(self):
        rng=random.Random(340034)
        with tempfile.TemporaryDirectory() as tmp:
            for task,g in self.programs.items():
                with self.subTest(task=task):
                    source=Path(tmp)/(task+'.c')
                    binary=Path(tmp)/(task+'.so')
                    source.write_text(native_source(g,task),encoding='utf-8')
                    p=subprocess.run(['gcc','-O3','-std=c11','-fPIC','-shared',
                                      '-Wall','-Wextra','-Werror',str(source),'-o',str(binary)],
                                     capture_output=True,text=True)
                    self.assertEqual(p.returncode,0,p.stderr)
                    lib=ctypes.CDLL(str(binary))
                    fn=lib.ag_generated
                    fn.argtypes=(ctypes.POINTER(ctypes.c_int64),ctypes.c_size_t,ctypes.c_int64)
                    fn.restype=ctypes.c_int64
                    for size in (0,1,2,3,16,64,128,512,4096):
                        for _ in range(6):
                            vals=tuple(rng.randint(-1000,1000) for _ in range(size))
                            if vals and rng.randrange(3)==0:
                                vals=(vals[0],)*size
                            array=(ctypes.c_int64*max(1,size))(*vals)
                            got=fn(array,size,0)
                            self.assertEqual(got,_task_oracle(task,vals))

    @unittest.skipUnless(shutil.which('gcc'), 'C compiler not available locally')
    def test_benchmark_raw_samples_and_ubsan_are_not_sota(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            from unittest.mock import patch
            # Use real v3.3 generator only; no task-specific solution injected.
            with patch('genome_headtail_v33.discover_headtail',
                       return_value=type('Generated',(),{'genome':self.programs['count_max']})()):
                outcome=run_benchmark('count_max',repetitions=2,
                        elements_per_sample=10000,output_dir=tmp)
            self.assertEqual(outcome['status'],'native_validated')
            self.assertEqual(outcome['ubsan'],'passed')
            self.assertEqual(outcome['raw_samples'],36)
            self.assertEqual(len(outcome['cells']),18)
            self.assertFalse(outcome['global_sota_claim'])
            self.assertFalse(outcome['novel_algorithm_claim'])
            for cell in outcome['cells']:
                self.assertGreater(cell['ratio_to_strong'],0)
                self.assertEqual(len(cell['samples']),2)
            for suffix in ('c','csv','json'):
                self.assertTrue((Path(tmp)/('v34_count_max.'+suffix)).exists())

    def test_bad_benchmark_budget_cannot_claim_result(self):
        for kwargs in ({'repetitions':0}, {'repetitions':True},
                       {'elements_per_sample':1}, {'task':'unknown'}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                run_benchmark(**kwargs)


if __name__=='__main__':
    unittest.main()
