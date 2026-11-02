"""v3.8: synthesize unconditional extrema-aggregation loops with typed select.

The generator explores a new control/data-flow family: both registers are
updated by conditional expressions in a loop with no conditional statements.
It filters complete executable ASTs through an independent task oracle.
Native timing selects only after correctness, and held-out cells run later.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory

from algorithm_genome_v30 import Expr, Genome, Machine, Stmt, atom, integer, op, to_dict, type_check, InvalidGenome, FuelExhausted
from genome_crossover_v32 import _cases, _task_oracle
from genome_headtail_v33 import discover_headtail
from native_autotune_v35 import TRAIN_CELLS, EVAL_CELLS
from native_benchmark_v34 import TASKS, native_source, run_benchmark
from native_blinded_v36 import _cell_map, _geomean, _summary


PROTOCOL='typed-select-v38-1'
TRAIN_SEED=0xC8437C09A65D201B
HOLDOUT_SEED=0x4DF7A2B9306CE185


def candidates():
    """Task-neutral expression grammar; no hard-coded winning solution."""
    x, best, count = atom('item'), atom('best'), atom('frequency')
    better_tests=(op('lt',best,x),op('lt',x,best))
    same_tests=(op('eq',x,best),op('eq',best,x))
    first_values=(integer(0),integer(1),Expr('read',(integer(0),)))
    reset_values=(integer(0),integer(1),x,best)
    increment_values=(integer(0),integer(1),x,best)
    for better,same,first,reset,increment,form,update_first,reverse in product(
            better_tests,same_tests,first_values,reset_values,
            increment_values,(0,1),(False,True),(False,True)):
        next_best=op('select',better,x,best)
        if form==0:
            next_count=op('select',better,reset,
                          op('add',count,op('select',same,increment,integer(0))))
        else:
            next_count=op('select',same,op('add',count,increment),
                          op('select',better,reset,count))
        updates=(Stmt('set',name='best',expr=next_best),
                 Stmt('set',name='frequency',expr=next_count))
        if not update_first:
            updates=updates[::-1]
        init=Stmt('if',cond=op('lt',integer(0),atom('length')),
                  then=(Stmt('set',name='best',expr=Expr('read',(integer(0),))),
                        Stmt('set',name='frequency',expr=first)))
        yield Genome((('best','int',integer(0)),
                      ('frequency','int',integer(0))),
                     (init,Stmt('foreach',start=1,reverse=reverse,then=updates)),
                     count,'int')


def _matches(machine,genome,task,cases):
    for values,key in cases:
        execution=machine.run(genome,values,key)
        if execution.value!=_task_oracle(task,values) or execution.final_array!=values:
            return False
    return True


def valid_genomes(task, *, seed=3201):
    if task not in TASKS or type(seed) is not int:
        raise ValueError('invalid task or seed')
    training,validation,_,_=_cases(seed)
    probes=(((),0),((-2,),0),((2,),0),((-2,-1),0),((2,-1),0),
            ((-2,-2),0),((2,2),0),((-2,0,-1),0),((2,0,1),0))
    machine=Machine()
    correct=[]
    proposals=0
    for genome in candidates():
        proposals+=1
        try:
            type_check(genome)
            if all(_matches(machine,genome,task,cases) for cases in (probes,training,validation)):
                correct.append(genome)
        except (InvalidGenome,FuelExhausted,IndexError):
            continue
    if not correct:
        raise AssertionError('new grammar found no correct programs')
    return proposals,tuple(correct)


@dataclass(frozen=True)
class Config:
    task:str='count_max'
    seed:int=3201
    max_profiles:int=6
    train_repetitions:int=3
    train_elements:int=150000
    holdout_repetitions:int=5
    holdout_elements:int=500000
    compiler:str='gcc'


def synthesize(config=Config(), *, output_dir=None, benchmark=run_benchmark):
    if not isinstance(config,Config) or config.task not in TASKS or type(config.seed) is not int:
        raise ValueError('invalid synthesis configuration')
    if type(config.max_profiles) is not int or not 2<=config.max_profiles<=16:
        raise ValueError('invalid native profile cap')
    if any(type(x) is not int or not 2<=x<=20 for x in
           (config.train_repetitions,config.holdout_repetitions)):
        raise ValueError('invalid repetitions')
    if any(type(x) is not int or not 10000<=x<=20000000 for x in
           (config.train_elements,config.holdout_elements)):
        raise ValueError('invalid work')
    if not isinstance(config.compiler,str) or not config.compiler:
        raise ValueError('invalid compiler')
    proposed,correct=valid_genomes(config.task,seed=config.seed)
    baseline=discover_headtail(config.task,seed=config.seed).genome
    distinct=tuple(dict.fromkeys(correct))
    if len(distinct)>config.max_profiles:
        indices=[i*(len(distinct)-1)//(config.max_profiles-1)
                 for i in range(config.max_profiles)]
        choices=tuple(distinct[i] for i in indices)
    else:
        choices=distinct
    if baseline in choices:
        raise AssertionError('select grammar did not expand the program structure')
    options=choices+(baseline,)
    destination=Path(output_dir) if output_dir is not None else None
    profiles=[]
    with TemporaryDirectory(prefix='ag-v38-') as tmp:
        temp=Path(tmp)
        def artifact(genome,name):
            path=temp/name
            path.write_text(json.dumps({'task':config.task,'candidate':to_dict(genome)}))
            return path
        for i,genome in enumerate(options):
            record={'index':i,'kind':'new_select' if i<len(choices) else 'v33_baseline',
                    'genome':to_dict(genome),'genome_nodes':genome.nodes()}
            try:
                report=benchmark(config.task,genome_json=artifact(genome,f'candidate_{i}.json'),
                    compiler=config.compiler,repetitions=config.train_repetitions,
                    elements_per_sample=config.train_elements,
                    cells=TRAIN_CELLS,data_seed=TRAIN_SEED)
                cells=_cell_map(report,TRAIN_CELLS)
                if report['data_seed']!=TRAIN_SEED:
                    raise AssertionError('selection data seed mismatch')
                record['score']=_geomean([cells[k]['ratio_to_strong'] for k in sorted(TRAIN_CELLS)])
                record['native_training_result']=report
            except (RuntimeError,ValueError,AssertionError) as exc:
                record['rejected']=str(exc)
            profiles.append(record)
        viable=[r for r in profiles if 'score' in r]
        novel=[r for r in viable if r['kind']=='new_select']
        if not novel or not any(r['kind']=='v33_baseline' for r in viable):
            raise AssertionError('missing correct native novel candidate or baseline')
        winner=min(viable,key=lambda r:(r['score'],r['genome_nodes'],r['index']))
        novel_best=min(novel,key=lambda r:(r['score'],r['genome_nodes'],r['index']))
        frozen_indices=tuple(dict.fromkeys((winner['index'],novel_best['index'],len(options)-1)))
        _,_,_,python_holdout=_cases(config.seed)
        machine=Machine()
        for i in frozen_indices:
            if not _matches(machine,options[i],config.task,python_holdout):
                raise AssertionError('frozen candidate failed independent Python holdout')
        evaluations={}
        for i in frozen_indices:
            genome=options[i]
            report=benchmark(config.task,genome_json=artifact(genome,f'holdout_{i}.json'),
                compiler=config.compiler,repetitions=config.holdout_repetitions,
                elements_per_sample=config.holdout_elements,
                cells=EVAL_CELLS,data_seed=HOLDOUT_SEED,
                output_dir=destination if i==winner['index'] else None)
            cells=_cell_map(report,EVAL_CELLS)
            if report['data_seed']!=HOLDOUT_SEED:
                raise AssertionError('holdout data seed mismatch')
            evaluations[str(i)]={'kind':profiles[i]['kind'],'summary':_summary(cells),
                                 'native_result':report}
    result={'protocol':PROTOCOL,'task':config.task,
            'status':'select_genome_experiment_complete',
            'grammar_proposals':proposed,'finite_verified_new_genomes':len(correct),
            'native_profiled_new':len(choices), 'native_profiled_total':len(options),
            'profiles':profiles,'selected_index':winner['index'],
            'best_new_index':novel_best['index'],
            'selected_kind':winner['kind'],
            'selected_genome':winner['genome'],
            'best_new_genome':novel_best['genome'],
            'v33_baseline_genome':to_dict(baseline),
            'training_seed':TRAIN_SEED,'holdout_seed':HOLDOUT_SEED,
            'independent_python_holdout_cases':len(python_holdout),
            'independent_python_holdout_passed':True,
            'training_cells':[list(x) for x in sorted(TRAIN_CELLS)],
            'holdout_cells':[list(x) for x in sorted(EVAL_CELLS)],
            'evaluations':evaluations,
            'global_novelty_claim':False,'global_sota_claim':False,
            'limitations':['new typed control/data-flow family, not a claim of worldwide algorithmic novelty',
                           'finite correctness corpus, no universal equivalence theorem',
                           'single compiler/machine repeated-array latency',
                           'selection uses existing scalar native references']}
    if destination is not None:
        destination.mkdir(parents=True,exist_ok=True)
        for label,genome in (('best_new',options[novel_best['index']]),
                             ('selected',options[winner['index']])):
            (destination/f'v38_{config.task}_{label}.c').write_text(
                native_source(genome,config.task),encoding='utf-8')
        (destination/f'v38_{config.task}.json').write_text(
            json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=TASKS,default='count_max')
    parser.add_argument('--max-profiles',type=int,default=6)
    parser.add_argument('--train-repetitions',type=int,default=3)
    parser.add_argument('--train-elements',type=int,default=150000)
    parser.add_argument('--holdout-repetitions',type=int,default=5)
    parser.add_argument('--holdout-elements',type=int,default=500000)
    parser.add_argument('--compiler',default='gcc')
    parser.add_argument('--output-dir',default='native_v38_evidence')
    args=parser.parse_args()
    config=Config(task=args.task,max_profiles=args.max_profiles,
                  train_repetitions=args.train_repetitions,train_elements=args.train_elements,
                  holdout_repetitions=args.holdout_repetitions,holdout_elements=args.holdout_elements,
                  compiler=args.compiler)
    result=synthesize(config,output_dir=args.output_dir)
    print(json.dumps({'task':result['task'],'new_genomes':result['finite_verified_new_genomes'],
                      'selected_kind':result['selected_kind'],
                      'best_new_holdout':result['evaluations'][str(result['best_new_index'])]['summary'],
                      'baseline_holdout':result['evaluations'][str(result['native_profiled_total']-1)]['summary']},
                     sort_keys=True))


if __name__=='__main__':
    main()
