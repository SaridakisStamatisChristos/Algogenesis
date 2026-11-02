"""v3.2 loop fusion: synthesize a one-pass program from two-pass genomes.

Replace two sequential scans with one typed scan that carries both states,
and enumerate reset expressions. This is a bounded search, not a universal
fusion theorem. All candidates are tested against independent task oracles.
"""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from algorithm_genome_v30 import Genome, Stmt, Machine, atom, integer, type_check, to_dict
from genome_crossover_v32 import (discover_composition, _cases, _task_oracle,
                                   _metrics, _independent_one_pass_reference)


@dataclass(frozen=True)
class FusionResult:
    task: str
    genome: Genome
    proposals: int
    correct: int
    baseline_metrics: tuple[float,float,float]
    fused_metrics: tuple[float,float,float]
    baseline_heldout: tuple[float,float,float]
    fused_heldout: tuple[float,float,float]
    strong_reference_comparisons: float
    status: str

    def report(self):
        return {'task':self.task,'status':self.status,
                'proposals':self.proposals,'correct_candidates':self.correct,
                'two_pass_fitness':list(self.baseline_metrics),
                'fused_fitness':list(self.fused_metrics),
                'two_pass_heldout':list(self.baseline_heldout),
                'fused_heldout':list(self.fused_heldout),
                'strong_one_pass_reference_comparisons':self.strong_reference_comparisons,
                'algorithm':to_dict(self.genome),
                'universal_correctness_proved':False,
                'global_optimality_proved':False,'sota_claim':False}


def fuse(task='count_max', *, seed=3201) -> FusionResult:
    """Fuse two generated loops with a searched reset expression.

    The predecessor independently generates both first-pass reducer and
    second-pass accumulator. Fusion retains the original condition, reducer
    updates, and second-loop body; it only composes their control flow.
    """
    original=discover_composition(task,seed=seed)
    base=original.genome
    if len(base.statements)!=2 or any(s.op!='foreach' for s in base.statements):
        raise ValueError('requires exactly two independent foreach stages')
    first,second=base.statements
    if len(first.then)!=1 or first.then[0].op!='if':
        raise ValueError('unsupported first-pass reducer')
    condition=first.then[0].cond
    updates=first.then[0].then
    training,validation,fitness,heldout=_cases(seed)
    vm=Machine()
    proposals=accepted=0
    pool=[]
    for reset in (integer(0),integer(1),atom('item'),atom('best')):
        proposals+=1
        branch=Stmt('if',cond=condition,
                    then=updates+(Stmt('set',name='frequency',expr=reset),),
                    otherwise=second.then)
        child=Genome(base.registers,
                     (Stmt('foreach',reverse=first.reverse,then=(branch,)),),
                     base.result,base.output_type)
        type_check(child)
        if any(vm.run(child,v,k).value!=_task_oracle(task,v) for v,k in training):
            continue
        if any(vm.run(child,v,k).value!=_task_oracle(task,v) for v,k in validation):
            continue
        accepted+=1
        pool.append((_metrics(vm,child,fitness),child))
    if not pool:
        raise AssertionError('bounded fusion grammar found no valid algorithm')
    best=min(pool,key=lambda x:(x[0],x[1].nodes(),repr(to_dict(x[1]))))
    for values,key in heldout:
        execution=vm.run(best[1],values,key)
        if execution.value!=_task_oracle(task,values) or execution.final_array!=values:
            raise AssertionError('independent withheld evaluation rejected fused genome')
    return FusionResult(task,best[1],proposals,accepted,
                        original.fitness,best[0],
                        original.heldout,_metrics(vm,best[1],heldout),
                        _independent_one_pass_reference(task,heldout),
                        'empirically_validated')


def main():
    parser=argparse.ArgumentParser(description='v3.2 typed one-pass fusion synthesis')
    parser.add_argument('--task',choices=('count_max','count_min','sum_max','sum_min'),
                        default='count_max')
    parser.add_argument('--output')
    args=parser.parse_args()
    data=fuse(args.task).report()
    rendered=json.dumps(data,indent=2,sort_keys=True)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(rendered+'\n',encoding='utf-8')
    print(rendered)


if __name__=='__main__':
    main()
