"""v3.6: selection-isolated native latency experiment.

The profiler executes only the six selection cells. The frozen evaluation
partition is opened once, after the winner is fixed, with a distinct seed.
The result remains a single-machine microbenchmark, not a SOTA claim.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from algorithm_genome_v30 import to_dict
from genome_headtail_v33 import discover_headtail
from native_autotune_v35 import TRAIN_CELLS, EVAL_CELLS, shortlist, valid_genomes
from native_benchmark_v34 import TASKS, run_benchmark


# Treat these values as a versioned protocol. Changing the partition or seed
# creates a new experiment; do not tune it after seeing results.
PROTOCOL='native-blinded-v36-1'
SELECTION_SEED=0x5A2026C0FFEE1234
HOLDOUT_SEED=0xD36A7C592B401E85


def _cell_map(report, expected):
    actual={(c['length'],c['distribution']):c for c in report['cells']}
    if len(report['cells'])!=len(expected) or set(actual)!=expected:
        raise AssertionError('runner accessed wrong native cell partition')
    if {tuple(c) for c in report['requested_cells']}!=expected:
        raise AssertionError('runner request/provenance mismatch')
    return actual


def _geomean(values):
    if not values or not all(math.isfinite(x) and x>0 for x in values):
        raise ValueError('invalid native latency ratio')
    return math.exp(sum(math.log(x) for x in values)/len(values))


def _summary(cells):
    ratios=[cells[k]['ratio_to_strong'] for k in sorted(cells)]
    return {'geometric_ratio_to_strong':_geomean(ratios),
            'cells_faster':sum(x<1 for x in ratios),
            'cells_slower':sum(x>1 for x in ratios),
            'cells_total':len(ratios)}


@dataclass(frozen=True)
class Config:
    task:str='count_max'
    seed:int=3201
    max_profiles:int=6
    selection_repetitions:int=3
    selection_elements:int=150000
    holdout_repetitions:int=5
    holdout_elements:int=500000
    compiler:str='gcc'


def run(config=Config(), *, output_dir=None, benchmark=run_benchmark):
    if not isinstance(config,Config) or config.task not in TASKS or type(config.seed) is not int:
        raise ValueError('invalid experiment configuration')
    if type(config.max_profiles) is not int or not 2<=config.max_profiles<=16:
        raise ValueError('invalid profile cap')
    if any(type(x) is not int or not 2<=x<=20 for x in
           (config.selection_repetitions,config.holdout_repetitions)):
        raise ValueError('invalid repetitions')
    if any(type(x) is not int or not 10000<=x<=20000000 for x in
           (config.selection_elements,config.holdout_elements)):
        raise ValueError('invalid benchmark work')
    if not isinstance(config.compiler,str) or not config.compiler:
        raise ValueError('invalid compiler')
    baseline=discover_headtail(config.task,seed=config.seed).genome
    proposed,correct=valid_genomes(config.task,seed=config.seed)
    options=shortlist(correct,baseline,config.max_profiles)
    records=[]
    destination=Path(output_dir) if output_dir is not None else None
    with TemporaryDirectory(prefix='ag-v36-') as tmp:
        temp=Path(tmp)
        for index,genome in enumerate(options):
            artifact=temp/f'candidate_{index}.json'
            artifact.write_text(json.dumps({'task':config.task,'candidate':to_dict(genome)}))
            record={'index':index,'genome':to_dict(genome),'genome_nodes':genome.nodes()}
            try:
                profile=benchmark(config.task,genome_json=artifact,compiler=config.compiler,
                    repetitions=config.selection_repetitions,
                    elements_per_sample=config.selection_elements,
                    cells=TRAIN_CELLS,data_seed=SELECTION_SEED)
                observed=_cell_map(profile,TRAIN_CELLS)
                if profile['data_seed']!=SELECTION_SEED:
                    raise AssertionError('selection seed mismatch')
                record['score']=_geomean([observed[k]['ratio_to_strong'] for k in sorted(TRAIN_CELLS)])
                record['selection_result']=profile
            except (RuntimeError,ValueError,AssertionError) as exc:
                record['rejected']=str(exc)
            records.append(record)
        viable=[r for r in records if 'score' in r]
        if not viable:
            raise AssertionError('all native candidates rejected')
        winner=min(viable,key=lambda r:(r['score'],r['genome_nodes'],r['index']))
        winner_index=winner['index']  # Freeze choice before any holdout invocation.
        def evaluate(genome, label, emit):
            artifact=temp/f'{label}.json'
            artifact.write_text(json.dumps({'task':config.task,'candidate':to_dict(genome)}))
            result=benchmark(config.task,genome_json=artifact,compiler=config.compiler,
                repetitions=config.holdout_repetitions,
                elements_per_sample=config.holdout_elements,
                cells=EVAL_CELLS,data_seed=HOLDOUT_SEED,output_dir=emit)
            observed=_cell_map(result,EVAL_CELLS)
            if result['data_seed']!=HOLDOUT_SEED:
                raise AssertionError('holdout seed mismatch')
            return result,observed
        chosen,chosen_cells=evaluate(options[winner_index],'winner',destination)
        base,base_cells=evaluate(baseline,'baseline',None)
    vs_baseline={str(k):chosen_cells[k]['median_ns_per_call']['generated_ns']/
                       base_cells[k]['median_ns_per_call']['generated_ns']
                 for k in sorted(EVAL_CELLS)}
    report={'protocol':PROTOCOL,'task':config.task,
        'status':'blinded_native_experiment_complete',
        'grammar_proposals':proposed,'finite_verified_genomes':len(correct),
        'profiled_candidates':records,'selected_index':winner_index,
        'selected_genome':to_dict(options[winner_index]),
        'v33_baseline_genome':to_dict(baseline),
        'selection_cells':[list(c) for c in sorted(TRAIN_CELLS)],
        'holdout_cells':[list(c) for c in sorted(EVAL_CELLS)],
        'selection_data_seed':SELECTION_SEED,'holdout_data_seed':HOLDOUT_SEED,
        'selection_score':winner['score'],
        'holdout_selected':_summary(chosen_cells),
        'holdout_v33':_summary(base_cells),
        'holdout_selected_over_v33_per_cell':vs_baseline,
        'selected_native_result':chosen,'baseline_native_result':base,
        'selection_measurements_exclude_holdout_cells':True,
        'global_sota_claim':False,
        'limitations':['single machine and compiler per run',
                       'warm-cache repeated-array microbenchmark',
                       'separate executable timings can drift',
                       'finite correctness screening, not universal proof',
                       'holdout protocol is public; freeze it before inspecting results']}
    if destination is not None:
        destination.mkdir(parents=True,exist_ok=True)
        (destination/f'v36_{config.task}.json').write_text(
            json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task',choices=TASKS,default='count_max')
    parser.add_argument('--max-profiles',type=int,default=6)
    parser.add_argument('--compiler',default='gcc')
    parser.add_argument('--selection-repetitions',type=int,default=3)
    parser.add_argument('--selection-elements',type=int,default=150000)
    parser.add_argument('--holdout-repetitions',type=int,default=5)
    parser.add_argument('--holdout-elements',type=int,default=500000)
    parser.add_argument('--output-dir',default='native_v36_evidence')
    args=parser.parse_args()
    config=Config(task=args.task,max_profiles=args.max_profiles,compiler=args.compiler,
                  selection_repetitions=args.selection_repetitions,
                  selection_elements=args.selection_elements,
                  holdout_repetitions=args.holdout_repetitions,
                  holdout_elements=args.holdout_elements)
    result=run(config,output_dir=args.output_dir)
    print(json.dumps({'task':result['task'],'status':result['status'],
                      'selected_index':result['selected_index'],
                      'holdout_selected':result['holdout_selected'],
                      'holdout_v33':result['holdout_v33']},sort_keys=True))


if __name__=='__main__':
    main()
