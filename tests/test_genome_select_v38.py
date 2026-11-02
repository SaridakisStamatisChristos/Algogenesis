"""Typed select semantics and genuinely expanded generator structure."""
import ctypes
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from algorithm_genome_v30 import (Expr, Genome, Machine, boolean, integer,
                                  op, to_dict, type_check, InvalidGenome)
from genome_headtail_v33 import candidates as old_candidates
from genome_select_v38 import Config, candidates, synthesize, valid_genomes
from native_codegen_v34 import compile_genome, decode_genome


class SelectGenomeTests(unittest.TestCase):
    def test_select_is_typed_and_evaluates_only_the_chosen_branch(self):
        read=Expr('read',(integer(0),))
        genome=Genome((),(),op('select',boolean(False),read,integer(7)),'int')
        type_check(genome)
        self.assertEqual(Machine().run(genome,(),0).value,7)
        self.assertEqual(decode_genome(json.loads(json.dumps(to_dict(genome)))),genome)
        for expression in (op('select',integer(1),integer(2),integer(3)),
                           op('select',boolean(True),integer(2),boolean(False)),
                           op('select',boolean(True),integer(2))):
            with self.subTest(expression=expression),self.assertRaises(InvalidGenome):
                type_check(Genome((),(),expression,'int'))

    def test_new_structural_family_and_independent_oracles(self):
        proposals=list(candidates())
        self.assertEqual(len(proposals),1536)
        old=set(old_candidates())
        self.assertFalse(any(g in old for g in proposals))
        for g in proposals:
            loop=g.statements[1]
            self.assertEqual(loop.op,'foreach')
            self.assertTrue(all(s.op=='set' and s.expr.op=='select'
                                for s in loop.then))
        for task,expected in (('count_max',8),('count_min',8),
                              ('sum_max',16),('sum_min',16)):
            with self.subTest(task=task):
                proposed,valid=valid_genomes(task)
                self.assertEqual((proposed,len(valid)),(1536,expected))
                self.assertTrue(all(g not in old for g in valid))

    @unittest.skipUnless(shutil.which('gcc'),'requires GCC')
    def test_native_select_short_circuit_and_real_search(self):
        read=Expr('read',(integer(0),))
        g=Genome((),(),op('select',boolean(False),read,integer(7)),'int')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'select.c'
            lib=Path(tmp)/'select.so'
            path.write_text(compile_genome(g))
            built=subprocess.run(['gcc','-std=c11','-O3','-Wall','-Wextra','-Werror',
                                  '-fPIC','-shared',str(path),'-o',str(lib)],
                                 capture_output=True,text=True)
            self.assertEqual(built.returncode,0,built.stderr)
            fn=ctypes.CDLL(str(lib)).ag_generated
            fn.argtypes=(ctypes.POINTER(ctypes.c_int64),ctypes.c_size_t,ctypes.c_int64)
            fn.restype=ctypes.c_int64
            self.assertEqual(fn(None,0,0),7)
            result=synthesize(Config(task='count_max',max_profiles=2,
                                     train_repetitions=2,train_elements=10000,
                                     holdout_repetitions=2,holdout_elements=10000),
                              output_dir=tmp)
            self.assertEqual(result['finite_verified_new_genomes'],8)
            self.assertEqual(result['native_profiled_total'],3)
            self.assertTrue(set(result['evaluations'])>={str(result['best_new_index']),
                                                        str(result['native_profiled_total']-1)})
            self.assertEqual(result['evaluations'][str(result['best_new_index'])]
                             ['summary']['cells_total'],12)
            self.assertFalse(result['global_novelty_claim'])
            self.assertFalse(result['global_sota_claim'])
            self.assertTrue((Path(tmp)/'v38_count_max.json').exists())
            self.assertTrue((Path(tmp)/'v38_count_max_best_new.c').exists())


if __name__=='__main__':
    unittest.main()
