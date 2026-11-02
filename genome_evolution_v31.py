"""v3.1: typed structural mutation, counterexample screening and multiobjective evolution.

Starts from a *generated* v3.0 genome. Generic transformations modify
expressions, branches, loops, state and arrays; no task-specific target
programs are embedded here. Correctness is empirical on bounded domains.
"""
from __future__ import annotations
import argparse
import json
import random
from dataclasses import dataclass, replace
from typing import Iterator

from algorithm_genome_v30 import (Expr, Stmt, Genome, Machine, InvalidGenome,
                                   FuelExhausted, atom, integer, boolean, op,
                                   discover, all_training_cases, oracle, type_check,
                                   to_dict)


def _expr_variants(e: Expr) -> Iterator[tuple[Expr, str]]:
    """Single-site expression mutations, without accessing task identity."""
    if e.op == 'int' and type(e.value) is int:
        for n in (-1, 0, 1):
            if n != e.value:
                yield integer(n), 'literal-change'
    if e.op == 'var' and e.value in ('item', 'key', 'index', 'length'):
        for name in ('item', 'key', 'index', 'length'):
            if name != e.value:
                yield atom(name), 'variable-rewire'
    for a, b in (('eq', 'lt'), ('lt', 'eq'), ('add', 'sub'),
                 ('sub', 'add'), ('and', 'or'), ('or', 'and')):
        if e.op == a:
            yield replace(e, op=b), 'operator-replace'
    if e.op == 'not' and e.args and e.args[0].op == 'not':
        yield e.args[0].args[0], 'double-negation'
    if e.op in ('and', 'or') and len(e.args) == 2:
        x, y = e.args
        neutral = boolean(True) if e.op == 'and' else boolean(False)
        if x == neutral:
            yield y, 'boolean-neutral-elimination'
        if y == neutral:
            yield x, 'boolean-neutral-elimination'
    if e.op in ('add', 'sub') and len(e.args) == 2 and e.args[1] == integer(0):
        yield e.args[0], 'integer-neutral-elimination'
    for index, child in enumerate(e.args):
        for variant, rule in _expr_variants(child):
            args = list(e.args)
            args[index] = variant
            yield replace(e, args=tuple(args)), 'subexpr/' + rule


def _statement_variants(s: Stmt) -> Iterator[tuple[Stmt, str]]:
    """Structure-changing operators applicable to multiple algorithm families."""
    for prop in ('expr', 'cond', 'stop_if', 'other'):
        e = getattr(s, prop)
        if e is not None:
            for variant, rule in _expr_variants(e):
                yield replace(s, **{prop: variant}), prop + '/' + rule
    if s.op == 'set' and s.expr is not None:
        e = s.expr
        # r += int(P) == if P: r += 1, with pure expressions and exact ints.
        if (e.op == 'add' and len(e.args) == 2 and
                e.args[0] == atom(s.name) and e.args[1].op == 'btoi' and
                len(e.args[1].args) == 1):
            condition = e.args[1].args[0]
            yield Stmt('if', cond=condition,
                       then=(Stmt('set', name=s.name,
                                  expr=op('add', atom(s.name), integer(1))),)), \
                  'predicate-increment-to-branch'
    if s.op == 'if' and s.cond is not None:
        yield replace(s, cond=op('not', s.cond), then=s.otherwise,
                      otherwise=s.then), 'invert-if'
        if not s.otherwise and len(s.then) == 1:
            action = s.then[0]
            if (action.op == 'set' and action.expr is not None and
                    action.expr.op == 'add' and len(action.expr.args) == 2 and
                    action.expr.args == (atom(action.name), integer(1))):
                yield Stmt('set', name=action.name,
                           expr=op('add', atom(action.name), op('btoi', s.cond))), \
                      'branch-to-predicate-increment'
    if s.op == 'foreach':
        yield replace(s, reverse=not s.reverse), 'reverse-loop'
        for cond in (None, atom('acc'), op('eq', atom('item'), atom('key'))):
            if cond != s.stop_if:
                yield replace(s, stop_if=cond), 'loop-stop-mutation'
    if s.op == 'store' and s.other is not None:
        for replacement in (integer(0), integer(1), atom('item'), atom('key')):
            if replacement != s.other:
                yield replace(s, other=replacement), 'array-write-mutation'
    for prop in ('then', 'otherwise'):
        statements = getattr(s, prop)
        for index, child in enumerate(statements):
            for variant, rule in _statement_variants(child):
                mutable = list(statements)
                mutable[index] = variant
                yield replace(s, **{prop: tuple(mutable)}), prop + '/' + rule
        for index in range(len(statements)):
            if s.op == 'if' or len(statements) > 1:
                yield replace(s, **{prop: statements[:index] + statements[index+1:]}), \
                      prop + '/delete-statement'
            if len(statements) < 3:
                yield replace(s, **{prop: statements[:index+1] +
                                      (statements[index],) + statements[index+1:]}), \
                      prop + '/duplicate-statement'


def mutations(g: Genome, *, cap: int = 600) -> Iterator[tuple[Genome, str]]:
    """Distinct, statically well-typed, single-edit offspring plus rule trail."""
    if type(cap) is not int or cap < 1:
        raise ValueError('invalid mutation cap')
    type_check(g)
    seen = {g}
    emitted = 0
    for index, (name, sort, initial) in enumerate(g.registers):
        for replacement, rule in _expr_variants(initial):
            registers = list(g.registers)
            registers[index] = (name, sort, replacement)
            candidate = replace(g, registers=tuple(registers))
            if candidate not in seen:
                try:
                    type_check(candidate)
                except InvalidGenome:
                    continue
                seen.add(candidate)
                yield candidate, 'register/' + rule
                emitted += 1
                if emitted >= cap:
                    return
    for index, statement in enumerate(g.statements):
        for replacement, rule in _statement_variants(statement):
            stmts = list(g.statements)
            stmts[index] = replacement
            candidate = replace(g, statements=tuple(stmts))
            if candidate not in seen:
                try:
                    type_check(candidate)
                except InvalidGenome:
                    continue
                seen.add(candidate)
                yield candidate, 'statement/' + rule
                emitted += 1
                if emitted >= cap:
                    return
    for variant, rule in _expr_variants(g.result):
        candidate = replace(g, result=variant)
        if candidate not in seen:
            try:
                type_check(candidate)
            except InvalidGenome:
                continue
            seen.add(candidate)
            yield candidate, 'result/' + rule
            emitted += 1
            if emitted >= cap:
                return


def _case_sets(seed: int):
    train = tuple(all_training_cases())
    rng = random.Random(seed + 39)
    validation = [(tuple(rng.randint(-17, 17) for _ in range(n)),
                   rng.randint(-17, 17)) for n in (0, 1, 2, 4, 8, 16, 32, 64)
                  for _ in range(4)]
    validation.extend((tuple([k] * n), k) for n in (1, 3, 10, 31, 64)
                      for k in (-11, 0, 11))
    validation.extend((tuple(range(n)), n+7) for n in (1, 8, 32, 64))
    fitness = tuple((tuple(([1] * n) + ([7] if hit else [])), 7)
                    for n in (4, 8, 16, 32, 64) for hit in (0, 1))
    fitness += tuple((tuple([(-3 if j % 3 else 7) for j in range(n)]), 7)
                     for n in (4, 8, 16, 32, 64))
    hold_rng = random.Random(seed + 104729)
    heldout = [(tuple(hold_rng.randint(-997, 997) for _ in range(n)),
                hold_rng.randint(-997, 997))
               for n in (0, 1, 2, 4, 8, 16, 32, 64) for _ in range(4)]
    heldout.extend((tuple([k] * n), k) for n in (1, 3, 10, 31, 64)
                   for k in (-1000, 0, 1000))
    heldout.extend((tuple(range(n)), n+19) for n in (1, 8, 32, 64))
    used = set(train) | set(validation) | set(fitness)
    disjoint = []
    for values, key in heldout:
        while (values, key) in used:
            values = tuple(v + 100000 for v in values)
            key += 100000
        used.add((values, key))
        disjoint.append((values, key))
    return train, tuple(validation), fitness, tuple(disjoint)


def _metrics(vm: Machine, g: Genome, data) -> tuple[float, float, float]:
    results = [vm.run(g, values, key) for values, key in data]
    n = len(results)
    return (sum(r.comparisons for r in results)/n,
            sum(r.writes for r in results)/n,
            sum(r.steps for r in results)/n)


def _objective(task: str, metrics: tuple[float, float, float], nodes: int):
    comparisons, writes, steps = metrics
    if task == 'clamp':
        return (writes, comparisons, steps, nodes)
    if task == 'sum':
        return (steps, comparisons, writes, nodes)
    return (comparisons, steps, writes, nodes)


def _matches(vm: Machine, g: Genome, task: str, values: tuple[int,...], key:int) -> bool:
    run = vm.run(g, values, key)
    actual = run.final_array if task == 'clamp' else run.value
    return actual == oracle(task, values, key) and (task == 'clamp' or
                                                    run.final_array == values)


@dataclass(frozen=True)
class EvolutionResult:
    task: str
    seed: int
    genome: Genome
    baseline: Genome
    proposals: int
    valid: int
    generations: int
    mutation_rules: tuple[str, ...]
    history: tuple[dict, ...]
    baseline_fitness: tuple[float, float, float]
    evolved_fitness: tuple[float, float, float]
    baseline_heldout: tuple[float, float, float]
    evolved_heldout: tuple[float, float, float]
    heldout_cases: int
    result: str

    def report(self) -> dict:
        return {'task': self.task, 'seed': self.seed,
                'status': self.result, 'proposals':self.proposals,
                'valid_candidates':self.valid, 'generations':self.generations,
                'mutation_rules':list(self.mutation_rules),
                'history':list(self.history),
                'fitness': {'base':list(self.baseline_fitness),
                            'evolved':list(self.evolved_fitness)},
                'heldout': {'cases':self.heldout_cases,
                            'base':list(self.baseline_heldout),
                            'evolved':list(self.evolved_heldout)},
                'baseline_genome':to_dict(self.baseline),
                'evolved_genome':to_dict(self.genome),
                'finite_scope_only':True,
                'global_novelty_claim':False,
                'global_optimality_claim':False}


def evolve(task='count', *, seed=1907, generations=3,
           beam=4, max_proposals=240, max_mutations=250) -> EvolutionResult:
    if (task not in ('count', 'contains', 'sum', 'clamp') or
            type(seed) is not int or type(generations) is not int or
            type(beam) is not int or type(max_proposals) is not int or
            type(max_mutations) is not int or not 1<=generations<=10 or
            not 1<=beam<=32 or not 1<=max_proposals<=5000 or
            not 1<=max_mutations<=1000):
        raise ValueError('invalid evolutionary search configuration')
    baseline_result = discover(task)
    if baseline_result.genome is None:
        raise RuntimeError('v3.0 seed algorithm not found')
    baseline = baseline_result.genome
    train, validation, fitness, heldout = _case_sets(seed)
    vm = Machine(fuel=20000, max_array=128)
    baseline_cost = _metrics(vm, baseline, fitness)
    current = baseline
    current_cost = baseline_cost
    proposals = valid = 0
    seen = {baseline}
    frontier = [baseline]
    improvements: list[dict] = []
    rules = set()
    for generation in range(generations):
        ranking = []
        exhausted = False
        for parent in frontier:
            for child, rule in mutations(parent, cap=max_mutations):
                if child in seen:
                    continue
                if proposals >= max_proposals:
                    exhausted = True
                    break
                seen.add(child)
                proposals += 1
                try:
                    if not _matches(vm, child, task, train[0][0], train[0][1]):
                        continue
                    if any(not _matches(vm,child,task,v,k) for v,k in train):
                        continue
                    if any(not _matches(vm,child,task,v,k) for v,k in validation):
                        continue
                    valid += 1
                    metrics = _metrics(vm, child, fitness)
                    score = _objective(task, metrics, child.nodes())
                    ranking.append((score, repr(to_dict(child)), child, rule, metrics))
                    rules.add(rule)
                    if score < _objective(task, current_cost, current.nodes()):
                        current, current_cost = child, metrics
                        improvements.append({'generation':generation+1, 'rule':rule,
                                             'objective':list(score),
                                             'nodes':child.nodes()})
                except (InvalidGenome, FuelExhausted, IndexError):
                    continue
            if exhausted:
                break
        if not ranking or exhausted:
            break
        ranking.sort(key=lambda row: (row[0],row[1]))
        frontier = [entry[2] for entry in ranking[:beam]]
    if any(not _matches(vm,current,task,v,k) for v,k in heldout):
        raise AssertionError('withheld evaluation discovered a real counterexample')
    if any(not _matches(vm,baseline,task,v,k) for v,k in heldout):
        raise AssertionError('v3.0 baseline failed held-out comparison')
    baseline_hold = _metrics(vm,baseline,heldout)
    evolved_hold = _metrics(vm,current,heldout)
    return EvolutionResult(task,seed,current,baseline,proposals,valid,
                           generations,tuple(sorted(rules)),tuple(improvements),
                           baseline_cost,current_cost,baseline_hold,evolved_hold,
                           len(heldout),'empirically_validated' if improvements
                           else 'no_fitness_improvement')


def main():
    parser = argparse.ArgumentParser(description='Bounded structural evolution of typed algorithm genomes')
    parser.add_argument('--task',choices=['count','contains','sum','clamp'],default='count')
    parser.add_argument('--seed',type=int,default=1907)
    parser.add_argument('--generations',type=int,default=3)
    parser.add_argument('--beam',type=int,default=4)
    parser.add_argument('--max-proposals',type=int,default=240)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = evolve(args.task,seed=args.seed,generations=args.generations,
                    beam=args.beam,max_proposals=args.max_proposals).report()
    serialized = json.dumps(report,sort_keys=True,indent=2)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(serialized+'\n',encoding='utf-8')
    print(serialized)


if __name__ == '__main__':
    main()
