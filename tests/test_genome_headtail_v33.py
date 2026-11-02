"""Adversarial regression gates for v3.3 head/tail algorithm synthesis."""
from dataclasses import replace
import itertools
import json
import random
import unittest

from algorithm_genome_v30 import (Genome, Stmt, Expr, Machine,
                                  integer, atom, type_check, InvalidGenome)
from genome_headtail_v33 import (candidates, discover_headtail, TASKS)
from genome_crossover_v32 import _task_oracle, _cases


class HeadTailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = {task:discover_headtail(task) for task in TASKS}

    def test_all_four_independently_generated_one_pass_programs(self):
        for task, result in self.results.items():
            with self.subTest(task=task):
                self.assertEqual(result.status, 'empirically_validated')
                self.assertEqual(result.proposed, 768)
                self.assertGreater(result.proved_by_testing, 0)
                self.assertEqual(result.heldout_cases, 51)
                self.assertEqual(result.genome.statements[1].start, 1)
                self.assertLess(result.heldout[0], result.prior_fused_comparisons)
                self.assertLess(result.heldout[1], result.prior_fused_steps)
                # Strong correctness-checked one-pass reference, not a weak strawman.
                self.assertLessEqual(result.heldout[0],
                                     result.comparison_reference * 1.15)
                self.assertFalse(result.report()['global_sota_claim'])
                self.assertFalse(result.report()['universal_formal_verification'])
                self.assertEqual(json.loads(json.dumps(result.report()))['task'], task)

    def test_exhaustive_small_arrays_and_independent_large_random(self):
        rng = random.Random(331)
        for task, result in self.results.items():
            vm = Machine()
            for n in range(5):
                for values in itertools.product((-2,-1,0,1,2),repeat=n):
                    self.assertEqual(vm.run(result.genome,values,0).value,
                                     _task_oracle(task,values))
            for n in (0,1,2,3,8,16,64,128):
                for _ in range(15):
                    values = tuple(rng.randint(-10**28,10**28) for i in range(n))
                    if values and rng.randrange(4)==0:
                        values = values[:1]*len(values)
                    output = vm.run(result.genome,values,0)
                    self.assertEqual(output.value,_task_oracle(task,values))
                    self.assertEqual(output.final_array,values)
                    self.assertEqual(output.writes,0)

    def test_early_iteration_skip_falsified_by_singletons(self):
        result=self.results['count_max']
        g=result.genome
        bad=replace(g,statements=(g.statements[0],
                     replace(g.statements[1],start=0)))
        self.assertEqual(Machine().run(g,(17,),0).value,1)
        self.assertEqual(Machine().run(bad,(17,),0).value,2)
        self.assertNotEqual(Machine().run(bad,(17,),0).value,
                            _task_oracle('count_max',(17,)))

    def test_unguarded_head_read_fails_empty_array(self):
        g=self.results['count_min'].genome
        unguarded=replace(g,statements=(g.statements[0].then[0], g.statements[1]))
        type_check(unguarded)
        with self.assertRaises(IndexError):
            Machine().run(unguarded,(),0)
        self.assertEqual(Machine().run(g,(),0).value,0)

    def test_start_index_semantics_and_type_checks(self):
        for start,reverse,expected in ((0,False,10),(1,False,9),
                                       (0,True,10),(1,True,9),(20,False,0)):
            expr=Expr('read',(atom('index'),))
            g=Genome((('acc','int',integer(0)),),
                     (Stmt('foreach', start=start,reverse=reverse,
                        then=(Stmt('set',name='acc',expr=Expr('add',
                              (atom('acc'),expr))),)),),atom('acc'),'int')
            type_check(g)
            arr=(1,2,3,4)
            observed=Machine().run(g,arr,0).value
            expected_result=sum(arr[start:])
            self.assertEqual(observed,expected_result)
        for bad in (-1,True,1.1,10001):
            g=replace(self.results['count_max'].genome,statements=(
                self.results['count_max'].genome.statements[0],
                replace(self.results['count_max'].genome.statements[1],start=bad)))
            with self.assertRaises(InvalidGenome):
                type_check(g)

    def test_corpus_separation_and_replication(self):
        a,b,c,d=_cases(3201)
        self.assertFalse(set(d)&set(a))
        self.assertFalse(set(d)&set(b))
        self.assertFalse(set(d)&set(c))
        self.assertEqual(discover_headtail('count_max'),self.results['count_max'])
        self.assertEqual(len(list(candidates())),768)

    def test_bounded_search_does_not_forge_success(self):
        with self.assertRaises(RuntimeError):
            discover_headtail('count_max',max_candidates=1)
        for args in ({'task':'unknown'}, {'task':'count_max','seed':True},
                     {'task':'count_max','max_candidates':0},
                     {'task':'count_max','max_candidates':True}):
            with self.subTest(args=args),self.assertRaises(ValueError):
                discover_headtail(**args)


if __name__=='__main__':
    unittest.main()
