"""Task-neutral algorithm synthesis, CEGIS, native code, and fail-closed gates."""
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from spec_synthesis_v40 import OracleDomain, TaskSpec, synthesize


def _spec(name, oracle, seed):
    rng=random.Random(seed)
    seen=set()
    parts={}
    for label,count in (('training',14),('validation',10),
                        ('challenge',20),('holdout',15)):
        cases=[]
        while len(cases)<count:
            values=tuple(rng.randint(-3,3) for _ in range(rng.randint(0,8)))
            key=rng.randint(-2,2)
            if (values,key) in seen:
                continue
            seen.add((values,key))
            cases.append({'values':list(values),'key':key,
                          'expected':oracle(values,key)})
        parts[label]=cases
    return TaskSpec.parse({'name':name,**parts})


class GeneralSynthesisTests(unittest.TestCase):
    def test_multiple_unwired_tasks_generate_distinct_algorithms(self):
        tasks={
            'count_key_custom':lambda v,k:v.count(k),
            'max_empty_zero_custom':lambda v,k:max(v) if v else 0,
            'alternating_sum_custom':lambda v,k:sum(x if i%2==0 else -x
                                                      for i,x in enumerate(v)),
        }
        generated=[]
        for name,oracle in tasks.items():
            with self.subTest(task=name):
                spec=_spec(name,oracle,460+len(name))
                report=synthesize(spec,oracle=oracle,
                    oracle_domain=OracleDomain(alphabet=(-2,0,2),
                                               keys=(-1,0,1),max_length=3))
                self.assertEqual(report['status'],'finite_spec_synthesis_complete')
                self.assertEqual(report['grammar_proposals'],4840)
                self.assertGreater(report['training_validation_survivors'],0)
                self.assertEqual(report['holdout_cases'],15)
                self.assertFalse(report['global_novelty_claim'])
                generated.append(report['genome'])
        self.assertEqual(len({json.dumps(g,sort_keys=True) for g in generated}),3)

    def test_counterexample_refinement_and_compiled_output(self):
        oracle=lambda v,k:sum(x for i,x in enumerate(v) if i%2==0 and x>0)
        def case(values):
            return {'values':values,'key':0,'expected':oracle(tuple(values),0)}
        spec=TaskSpec.parse({'name':'sparse_even_positive',
            'training':[case([]),case([1]),case([2]),case([1,-3])],
            'validation':[case([-1]),case([2,5])],
            'challenge':[],
            'holdout':[case([0,10,3]),case([-2,9,4])]})
        with tempfile.TemporaryDirectory() as tmp:
            report=synthesize(spec,oracle=oracle,
                oracle_domain=OracleDomain(alphabet=(-2,0,2),keys=(0,),max_length=4),
                native_compiler='gcc' if shutil.which('gcc') else None,
                output_dir=tmp)
            self.assertGreater(report['counterexamples_added'],0)
            self.assertEqual(report['holdout_cases'],2)
            self.assertTrue((Path(tmp)/'v40_sparse_even_positive.c').exists())
            self.assertTrue((Path(tmp)/'v40_sparse_even_positive.json').exists())
            if shutil.which('gcc'):
                self.assertEqual(report['native_verification']['ubsan'],'passed')
                self.assertGreater(report['native_verification']['cases'],100)

    def test_json_example_is_not_task_name_routing(self):
        path=Path(__file__).parents[1]/'examples/positive_even_sum_v40.json'
        original=json.loads(path.read_text(encoding='utf-8'))
        a=synthesize(TaskSpec.parse(original))
        original['name']='renamed_arbitrary_task'
        b=synthesize(TaskSpec.parse(original))
        self.assertEqual(a['genome'],b['genome'])
        self.assertEqual(a['holdout_cases'],30)

    def test_oracle_domain_does_not_expose_holdout_during_search(self):
        spec=TaskSpec.parse({'name':'holdout_seal',
            'training':[{'values':[],'key':1,'expected':0},
                        {'values':[1,2],'key':0,'expected':3},
                        {'values':[2,3],'key':1,'expected':5}],
            'validation':[{'values':[3,4],'key':0,'expected':7},
                          {'values':[-1,2],'key':0,'expected':1}],
            'challenge':[],
            'holdout':[{'values':[2],'key':0,'expected':2}]})
        def oracle(values,key):
            return 999 if values==(2,) else sum(values)
        report=synthesize(spec,oracle=oracle,
            oracle_domain=OracleDomain(alphabet=(2,),keys=(0,),max_length=1))
        self.assertEqual(report['challenge_cases'],1)
        self.assertEqual(report['holdout_cases'],1)

    def test_invalid_specs_and_false_holdout_fail_closed(self):
        case={'values':[],'key':0,'expected':0}
        base={'name':'sample','training':[case],
              'validation':[{'values':[1],'key':0,'expected':0}],
              'challenge':[],
              'holdout':[{'values':[2],'key':0,'expected':999}]}
        spec=TaskSpec.parse(base)
        with self.assertRaisesRegex(RuntimeError,'held-out'):
            synthesize(spec)
        for malformed in (
            {**base,'name':'../escape'},
            {**base,'validation':[case]},
            {**base,'training':[{'values':[True],'key':0,'expected':0}]},
            {**base,'training':[{'values':[],'key':0,'expected':1<<80}]},
        ):
            with self.subTest(malformed=malformed),self.assertRaises(ValueError):
                TaskSpec.parse(malformed)


if __name__=='__main__':
    unittest.main()
