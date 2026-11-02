"""v3.9: discover two-lane extrema aggregators from partial-summary grammar.

Even and odd positions maintain independent extrema and multiplicities.
The result expression merges those summaries. The grammar varies all update
values, comparison directions and branch order; an independent oracle accepts
complete programs, rather than installing a task-specific solution.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory

from algorithm_genome_v30 import (Expr, Genome, Machine, Stmt, atom, integer,
                                  op, to_dict, type_check, InvalidGenome, FuelExhausted)
from genome_crossover_v32 import _cases, _metrics, _task_oracle
from native_autotune_v35 import EVAL_CELLS
from native_benchmark_v34 import TASKS, run_benchmark
from native_blinded_v36 import _cell_map, _summary

PROTOCOL='striped-summary-v39-1'
NATIVE_SEED=0xB6710F4C8D239EA5


def _lane_body(lane,better,same,reset,increment,equal_first):
    best=atom('best'+lane)
    frequency=atom('frequency'+lane)
    x=atom('item')
    greater=op('lt',best,x) if better==0 else op('lt',x,best)
    equals=op('eq',x,best) if same==0 else op('eq',best,x)
    reset_to=(integer(0),integer(1),x,best)[reset]
    add_value=(integer(0),integer(1),x,best)[increment]
    update_better=(Stmt('set',name='best'+lane,expr=x),
                   Stmt('set',name='frequency'+lane,expr=reset_to))
    update_equal=(Stmt('set',name='frequency'+lane,
                       expr=op('add',frequency,add_value)),)
    if equal_first:
        return (Stmt('if',cond=equals,then=update_equal,
                     otherwise=(Stmt('if',cond=greater,then=update_better),)),)
    return (Stmt('if',cond=greater,then=update_better,
                 otherwise=(Stmt('if',cond=equals,then=update_equal),)),)


def candidates():
    """Task-neutral cross-product of local summaries and merge expressions."""
    length=atom('length')
    f0,f1=atom('frequency0'),atom('frequency1')
    b0,b1=atom('best0'),atom('best1')
    for better,same,first,reset,increment,equal_first,reverse,merge in product(
            range(2),range(2),range(3),range(4),range(4),
            (False,True),(False,True),range(2)):
        first0=(integer(0),integer(1),Expr('read',(integer(0),)))[first]
        first1=(integer(0),integer(1),Expr('read',(integer(1),)))[first]
        take0=op('lt',b1,b0) if merge==0 else op('lt',b0,b1)
        take1=op('lt',b0,b1) if merge==0 else op('lt',b1,b0)
        merged=op('select',take0,f0,
                  op('select',take1,f1,op('add',f0,f1)))
        result=op('select',op('lt',length,integer(1)),integer(0),
                  op('select',op('lt',length,integer(2)),f0,merged))
        init0=Stmt('if',cond=op('lt',integer(0),length),then=(
            Stmt('set',name='best0',expr=Expr('read',(integer(0),))),
            Stmt('set',name='frequency0',expr=first0)))
        init1=Stmt('if',cond=op('lt',integer(1),length),then=(
            Stmt('set',name='best1',expr=Expr('read',(integer(1),))),
            Stmt('set',name='frequency1',expr=first1)))
        parity=op('eq',op('band',atom('index'),integer(1)),integer(0))
        scan=Stmt('foreach',start=2,reverse=reverse,then=(
            Stmt('if',cond=parity,
                 then=_lane_body('0',better,same,reset,increment,equal_first),
                 otherwise=_lane_body('1',better,same,reset,increment,equal_first)),))
        yield Genome((('best0','int',integer(0)),('frequency0','int',integer(0)),
                      ('best1','int',integer(0)),('frequency1','int',integer(0))),
                     (init0,init1,scan),result,'int')


def _matches(vm,genome,task,cases):
    for values,key in cases:
        result=vm.run(genome,values,key)
        if result.value!=_task_oracle(task,values) or result.final_array!=values:
            return False
    return True


@dataclass(frozen=True)
class Result:
    task:str
    genome:Genome
    proposed:int
    correct:int
    fitness:tuple[float,float,float]
    python_holdout_cases:int


def discover(task='count_max', *, seed=3201):
    if task not in TASKS or type(seed) is not int:
        raise ValueError('invalid task or seed')
    training,validation,fitness,holdout=_cases(seed)
    probes=(((),0),((-2,),0),((2,),0),((-2,-1),0),((2,-1),0),
            ((-2,-2),0),((2,2),0),((-2,0,-1),0),((2,0,1),0),
            ((1,3,5,3,1,5),0),((-3,4,-3,4),0))
    vm=Machine()
    proposed=correct=0
    best=None
    best_score=None
    for genome in candidates():
        proposed+=1
        try:
            type_check(genome)
            if not all(_matches(vm,genome,task,cases) for cases in
                       (probes,training,validation)):
                continue
            correct+=1
            metric=_metrics(vm,genome,fitness)
            score=(*metric,genome.nodes(),repr(to_dict(genome)))
            if best_score is None or score<best_score:
                best,best_score=genome,score
        except (InvalidGenome,FuelExhausted,IndexError):
            continue
    if best is None:
        raise AssertionError('no independently correct striped genome')
    if not _matches(vm,best,task,holdout):
        raise AssertionError('striped candidate failed independent holdout')
    return Result(task,best,proposed,correct,tuple(best_score[:3]),len(holdout))


def experiment(task='count_max', *, seed=3201, repetitions=5,
               elements_per_sample=500000, compiler='gcc', output_dir=None):
    result=discover(task,seed=seed)
    destination=Path(output_dir) if output_dir is not None else None
    with TemporaryDirectory(prefix='ag-v39-') as tmp:
        artifact=Path(tmp)/'striped.json'
        artifact.write_text(json.dumps({'task':task,'candidate':to_dict(result.genome)}))
        native=run_benchmark(task,genome_json=artifact,compiler=compiler,
            repetitions=repetitions,elements_per_sample=elements_per_sample,
            cells=EVAL_CELLS,data_seed=NATIVE_SEED,output_dir=destination)
    cells=_cell_map(native,EVAL_CELLS)
    if native['data_seed']!=NATIVE_SEED:
        raise AssertionError('native seed provenance mismatch')
    report={'protocol':PROTOCOL,'task':task,'status':'striped_genome_generated',
            'grammar_proposals':result.proposed,
            'finite_verified_genomes':result.correct,
            'selected_genome':to_dict(result.genome),
            'fitness_operations':result.fitness,
            'independent_python_holdout_cases':result.python_holdout_cases,
            'native_seed':NATIVE_SEED,'native_result':native,
            'native_summary':_summary(cells),
            'global_novelty_claim':False,'global_sota_claim':False,
            'limitations':['two-lane summary algorithm is new to this generator, not necessarily novel in literature',
                           'finite Python/C checks, no universal proof',
                           'single CPU and compiler warm-array microbenchmark']}
    if destination is not None:
        destination.mkdir(parents=True,exist_ok=True)
        (destination/f'v39_{task}.json').write_text(
            json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=TASKS,default='count_max')
    parser.add_argument('--repetitions',type=int,default=5)
    parser.add_argument('--elements-per-sample',type=int,default=500000)
    parser.add_argument('--compiler',default='gcc')
    parser.add_argument('--output-dir',default='native_v39_evidence')
    args=parser.parse_args()
    report=experiment(args.task,repetitions=args.repetitions,
                      elements_per_sample=args.elements_per_sample,
                      compiler=args.compiler,output_dir=args.output_dir)
    print(json.dumps({'task':args.task,'proposed':report['grammar_proposals'],
                      'correct':report['finite_verified_genomes'],
                      'native_summary':report['native_summary']},sort_keys=True))


if __name__=='__main__':
    main()
