"""v3.5: native-guided selection among independently verified typed genomes.

Search uses the existing v3.3 task-independent program grammar and the
v3.4 GCC native benchmark. Selection reads only six tuning cells; the
other 12 cells are withheld from ranking and reported only after selection.
Native latency improvements are empirical, machine-specific, and may not
generalize. Never claim global optimality or SOTA.
"""
from __future__ import annotations
import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from algorithm_genome_v30 import Machine, to_dict, type_check, InvalidGenome, FuelExhausted
from genome_headtail_v33 import candidates, discover_headtail
from genome_crossover_v32 import _cases, _task_oracle
from native_benchmark_v34 import run_benchmark, TASKS


TRAIN_CELLS=frozenset((length, distribution)
    for length in (16,128)
    for distribution in ('uniform','duplicates','all_equal'))
EVAL_CELLS=frozenset((length, distribution)
    for length in (16,128,1024)
    for distribution in ('increasing','decreasing','alternating')) | frozenset(
    (1024, distribution)
    for distribution in ('uniform','duplicates','all_equal'))


def _matches(machine, genome, task, cases):
    for values, key in cases:
        result=machine.run(genome,values,key)
        if result.value!=_task_oracle(task,values) or result.final_array!=values:
            return False
    return True


def valid_genomes(task, *, seed=3201):
    """Enumerate typed genomes; filter independently by task oracle only."""
    if task not in TASKS or type(seed) is not int:
        raise ValueError('invalid discovery task/seed')
    training, validation, _, _ = _cases(seed)
    probes=(((),0),((-2,),0),((2,),0),((-2,-1),0),((2,-1),0),
            ((-2,-2),0),((2,2),0),((-2,0,-1),0),((2,0,1),0))
    machine=Machine()
    valid=[]
    proposed=0
    for genome in candidates():
        proposed+=1
        try:
            type_check(genome)
            if not _matches(machine,genome,task,probes):
                continue
            if not _matches(machine,genome,task,training):
                continue
            if not _matches(machine,genome,task,validation):
                continue
            valid.append(genome)
        except (InvalidGenome, FuelExhausted, IndexError):
            continue
    if not valid:
        raise AssertionError('no verified genome variants')
    return proposed,tuple(valid)


def shortlist(pool,baseline,limit):
    """Evenly spaced deterministic candidate sample; retain v3.3 baseline."""
    if type(limit) is not int or not 2<=limit<=16:
        raise ValueError('invalid native profile budget')
    if baseline not in pool:
        raise AssertionError('baseline absent from verified grammar')
    distinct=list(dict.fromkeys(pool))
    if len(distinct)<=limit:
        return tuple(distinct)
    indices=[(i*(len(distinct)-1))//(limit-1) for i in range(limit)]
    choices=[distinct[i] for i in indices]
    if baseline not in choices:
        choices[-1]=baseline
    return tuple(dict.fromkeys(choices))


def partition(cells):
    selected={}
    withheld={}
    for cell in cells:
        key=(cell['length'],cell['distribution'])
        if key in TRAIN_CELLS:
            selected[key]=cell
        elif key in EVAL_CELLS:
            withheld[key]=cell
        else:
            raise AssertionError('unspecified benchmark cell')
    if set(selected)!=TRAIN_CELLS or set(withheld)!=EVAL_CELLS:
        raise AssertionError('incomplete/overlapping native evaluation cells')
    return selected,withheld


def score_selection(training_cells):
    if set(training_cells)!=TRAIN_CELLS:
        raise ValueError('selection restricted to six predeclared training cells')
    ratios=[training_cells[key]['ratio_to_strong']
            for key in sorted(TRAIN_CELLS)]
    if not all(math.isfinite(x) and x>0 for x in ratios):
        raise ValueError('nonpositive or nonfinite speed ratio')
    return math.exp(sum(math.log(x) for x in ratios)/len(ratios))


def holdout_summary(cells):
    if set(cells)!=EVAL_CELLS:
        raise ValueError('require all twelve held-out cells')
    vals=[cells[key]['ratio_to_strong'] for key in sorted(EVAL_CELLS)]
    return {'geometric_ratio_to_strong':math.exp(sum(math.log(x) for x in vals)/len(vals)),
            'cells_faster':sum(x<1 for x in vals),
            'cells_slower':sum(x>1 for x in vals),
            'cells_total':len(vals)}


@dataclass(frozen=True)
class SearchConfig:
    task:str='count_max'
    seed:int=3201
    max_profiles:int=6
    training_repetitions:int=3
    training_elements:int=150000
    final_repetitions:int=5
    final_elements:int=500000


def autotune(config=SearchConfig(), *, output_dir=None):
    if not isinstance(config,SearchConfig) or config.task not in TASKS or type(config.seed) is not int:
        raise ValueError('invalid tuning configuration')
    if type(config.max_profiles) is not int or not 2<=config.max_profiles<=16:
        raise ValueError('invalid profile cap')
    if type(config.training_repetitions) is not int or not 2<=config.training_repetitions<=20:
        raise ValueError('invalid profile repetitions')
    if type(config.final_repetitions) is not int or not 2<=config.final_repetitions<=20:
        raise ValueError('invalid final repetitions')
    if any(type(x) is not int or not 10000<=x<=20000000
           for x in (config.training_elements,config.final_elements)):
        raise ValueError('invalid benchmark work')
    baseline=discover_headtail(config.task,seed=config.seed).genome
    proposed,correct=valid_genomes(config.task,seed=config.seed)
    options=shortlist(correct,baseline,config.max_profiles)
    evaluations=[]
    with TemporaryDirectory(prefix='ag-native-variants-') as temporary:
        for index,genome in enumerate(options):
            path=Path(temporary)/('variant_'+str(index)+'.json')
            path.write_text(json.dumps({'task':config.task,
                                        'candidate':to_dict(genome)}),encoding='utf-8')
            try:
                report=run_benchmark(config.task,genome_json=path,
                    repetitions=config.training_repetitions,
                    elements_per_sample=config.training_elements)
                training,_=partition(report['cells'])
                rank=score_selection(training)
                evaluations.append({'index':index,'rank':rank,
                    'genome_nodes':genome.nodes(),'genome':genome,
                    'training_cells':{str(k):training[k]['ratio_to_strong']
                                      for k in sorted(training)}})
            except (RuntimeError,AssertionError,ValueError) as exc:
                evaluations.append({'index':index,'rejected':str(exc)})
        survivors=[x for x in evaluations if 'rank' in x]
        if not survivors:
            raise AssertionError('all native candidates rejected')
        winner=min(survivors,key=lambda x:(x['rank'],x['genome_nodes'],x['index']))
        winner_index=winner['index']
        selected=options[winner_index]
        selected_path=Path(temporary)/('selected.json')
        selected_path.write_text(json.dumps({'task':config.task,
                                             'candidate':to_dict(selected)}),encoding='utf-8')
        base_path=Path(temporary)/('baseline.json')
        base_path.write_text(json.dumps({'task':config.task,
                                         'candidate':to_dict(baseline)}),encoding='utf-8')
        destination=Path(output_dir) if output_dir is not None else None
        # Final repeats are distinct from tuning repetitions. The final
        # heldout cells are never consulted to choose the winner.
        chosen=run_benchmark(config.task,genome_json=selected_path,
            repetitions=config.final_repetitions,
            elements_per_sample=config.final_elements,
            output_dir=destination)
        reference=run_benchmark(config.task,genome_json=base_path,
            repetitions=config.final_repetitions,
            elements_per_sample=config.final_elements)
    _,chosen_eval=partition(chosen['cells'])
    _,base_eval=partition(reference['cells'])
    summary=holdout_summary(chosen_eval)
    base_summary=holdout_summary(base_eval)
    gain_vs_v33={str(k):chosen_eval[k]['median_ns_per_call']['generated_ns']/
                           base_eval[k]['median_ns_per_call']['generated_ns']
                  for k in sorted(EVAL_CELLS)}
    # Always report losses. Separate runner processes are a limitation.
    result={'task':config.task,'status':'native_experiment_complete',
            'grammar_proposals':proposed,'finite_verified_genomes':len(correct),
            'native_profiled':len(options),'selected_index':winner_index,
            'profiled_candidates':[
                {k:v for k,v in record.items() if k!='genome'}
                for record in evaluations],
            'training_best_geomean_ratio':winner['rank'],
            'selected_genome':to_dict(selected),
            'v33_baseline_genome':to_dict(baseline),
            'heldout_selected':summary,'heldout_v33':base_summary,
            'heldout_selected_over_v33_per_cell':gain_vs_v33,
            'selected_native_result':chosen,
            'baseline_native_result':reference,
            'training_cells':sorted([list(k) for k in TRAIN_CELLS]),
            'evaluation_cells':sorted([list(k) for k in EVAL_CELLS]),
            'native_latency_search':True,
            'selected_on_heldout':False,
            'global_sota_claim':False,'novel_algorithm_claim':False,
            'limitations':['single CI CPU and compiler environment',
                           'warm-cache repeated-array native microbenchmarks',
                           'separate executable timings can have drift',
                           'limited 768-genome grammar for four task families']}
    if output_dir is not None:
        Path(output_dir).mkdir(parents=True,exist_ok=True)
        (Path(output_dir)/('v35_'+config.task+'.json')).write_text(
            json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='v3.5 native-guided algorithm genome autotuning')
    p.add_argument('--task',choices=TASKS,default='count_max')
    p.add_argument('--max-profiles',type=int,default=6)
    p.add_argument('--training-repetitions',type=int,default=3)
    p.add_argument('--training-elements',type=int,default=150000)
    p.add_argument('--final-repetitions',type=int,default=5)
    p.add_argument('--final-elements',type=int,default=500000)
    p.add_argument('--output-dir',default='native_v35_evidence')
    args=p.parse_args()
    config=SearchConfig(task=args.task,max_profiles=args.max_profiles,
         training_repetitions=args.training_repetitions,
         training_elements=args.training_elements,
         final_repetitions=args.final_repetitions,
         final_elements=args.final_elements)
    report=autotune(config,output_dir=args.output_dir)
    print(json.dumps({'task':report['task'],'status':report['status'],
        'selected_index':report['selected_index'],
        'training_score':report['training_best_geomean_ratio'],
        'heldout_selected':report['heldout_selected'],
        'heldout_v33':report['heldout_v33']},sort_keys=True))


if __name__=='__main__':
    main()
