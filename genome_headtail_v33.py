"""v3.3: discover head/tail one-pass array algorithms with a typed grammar.

Unlike v3.2 fused scans, the generated program initializes from the
first element (only when nonempty), then scans from index 1. Search
enumerates distinct compare/branch orders and update expressions;
the independent oracle must validate each entire executable genome.

The 51 held-out cases are never used in candidate search or ranking.
Evidence of SOTA, optimality, universal proof or native latency is absent.
"""
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass
from itertools import product
from algorithm_genome_v30 import (Genome, Stmt, Expr, Machine, atom, integer,
    op, type_check, to_dict, InvalidGenome, FuelExhausted)
from genome_crossover_v32 import _cases, _task_oracle, _metrics, _independent_one_pass_reference
from genome_fusion_v32 import fuse

TASKS = ('count_max', 'count_min', 'sum_max', 'sum_min')


def candidates():
    """Generic typed expression/control-flow grammar; no task-dependent solutions.

    The two possible comparison orders, update directions, reset and
    increment expressions are all explored for every task.
    """
    x = atom('item')
    best = atom('best')
    frequency = atom('frequency')
    comparison = (op('lt', best, x), op('lt', x, best))
    equals = (op('eq', x, best), op('eq', best, x))
    first_values = (integer(0), integer(1), Expr('read', (integer(0),)))
    reset_values = (integer(0), integer(1), x, best)
    increment_values = (integer(0), integer(1), x, best)
    for greater, same, first, reset, increment, equal_first, backwards in product(
            comparison, equals, first_values, reset_values, increment_values,
            (False, True), (False, True)):
        take_better = (Stmt('set', name='best', expr=x),
                       Stmt('set', name='frequency', expr=reset))
        take_equal = (Stmt('set', name='frequency',
                           expr=op('add', frequency, increment)),)
        if equal_first:
            decision = Stmt('if', cond=same, then=take_equal,
                            otherwise=(Stmt('if', cond=greater,
                                            then=take_better),))
        else:
            decision = Stmt('if', cond=greater, then=take_better,
                            otherwise=(Stmt('if', cond=same,
                                            then=take_equal),))
        initialization = Stmt(
            'if', cond=op('lt', integer(0), atom('length')),
            then=(Stmt('set', name='best',
                       expr=Expr('read', (integer(0),))),
                  Stmt('set', name='frequency', expr=first)))
        loop = Stmt('foreach', start=1, reverse=backwards, then=(decision,))
        yield Genome((('best', 'int', integer(0)),
                      ('frequency', 'int', integer(0))),
                     (initialization, loop), frequency, 'int')


def _correct(vm, g, task, cases):
    for values, key in cases:
        result = vm.run(g, values, key)
        if result.value != _task_oracle(task, values) or result.final_array != values:
            return False
    return True


@dataclass(frozen=True)
class HeadTailResult:
    task: str
    genome: Genome
    proposed: int
    proved_by_testing: int
    fitness: tuple[float, float, float]
    heldout: tuple[float, float, float]
    heldout_cases: int
    comparison_reference: float
    prior_fused_comparisons: float
    prior_fused_steps: float
    certified_pattern: str
    status: str

    def report(self):
        return {
            'task': self.task, 'status': self.status,
            'generated_candidates': self.proposed,
            'correct_training_validation': self.proved_by_testing,
            'fitness_operations': list(self.fitness),
            'heldout_operations': list(self.heldout),
            'heldout_cases': self.heldout_cases,
            'strong_one_pass_reference_comparisons': self.comparison_reference,
            'v32_fused_comparisons': self.prior_fused_comparisons,
            'v32_fused_steps': self.prior_fused_steps,
            'candidate': to_dict(self.genome),
            'pattern': self.certified_pattern,
            'heldout_only_for_reporting': True,
            'finite_oracle_validation': True,
            'universal_formal_verification': False,
            'global_sota_claim': False,
            'novel_algorithm_claim': False,
        }


def discover_headtail(task='count_max', *, seed=3201, max_candidates=3000):
    if task not in TASKS or type(seed) is not int or type(max_candidates) is not int or not 1 <= max_candidates <= 10000:
        raise ValueError('invalid v3.3 research configuration')
    training, validation, fitness, withheld = _cases(seed)
    vm = Machine()
    proposals = valid = 0
    # Early examples include empty, one-element, better, worse, repeated,
    # signed and reverse-order arrays. They are all in the training corpus.
    probes = (((), 0), ((-2,), 0), ((2,), 0), ((-2, -1), 0),
              ((2, -1), 0), ((-2, -2), 0), ((2, 2), 0),
              ((-2, 0, -1), 0), ((2, 0, 1), 0))
    winner = None
    winner_score = None
    for g in candidates():
        if proposals >= max_candidates:
            break
        proposals += 1
        try:
            type_check(g)
            if not _correct(vm, g, task, probes):
                continue
            if not _correct(vm, g, task, training):
                continue
            if not _correct(vm, g, task, validation):
                continue
            valid += 1
            fitness_metric = _metrics(vm, g, fitness)
            score = (fitness_metric[0], fitness_metric[1],
                     fitness_metric[2], g.nodes(), repr(to_dict(g)))
            if winner_score is None or score < winner_score:
                winner = g
                winner_score = score
        except (InvalidGenome, FuelExhausted, IndexError):
            continue
    if winner is None:
        raise RuntimeError('bounded grammar found no correct one-pass program')
    # Withheld cases are checked once after winner selection; not adaptive.
    if not _correct(vm, winner, task, withheld):
        raise AssertionError('held-out counterexample: candidate must fail closed')
    held_metric = _metrics(vm, winner, withheld)
    fused = fuse(task, seed=seed)
    reference = _independent_one_pass_reference(task, withheld)
    return HeadTailResult(
        task, winner, proposals, valid, tuple(winner_score[:3]),
        held_metric, len(withheld), reference, fused.fused_heldout[0],
        fused.fused_heldout[1], 'first-element-guard + exclusive-tail-loop',
        'empirically_validated')


def main():
    p = argparse.ArgumentParser(description='AlgoGenesis v3.3 typed one-pass generator')
    p.add_argument('--task', choices=TASKS, default='count_max')
    p.add_argument('--max-candidates', type=int, default=3000)
    p.add_argument('--output')
    a = p.parse_args()
    report = discover_headtail(a.task, max_candidates=a.max_candidates).report()
    payload = json.dumps(report, indent=2, sort_keys=True)
    if a.output:
        from pathlib import Path
        Path(a.output).write_text(payload + '\n', encoding='utf-8')
    print(payload)


if __name__ == '__main__':
    main()
