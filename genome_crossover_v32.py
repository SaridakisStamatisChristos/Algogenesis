"""v3.2: bounded typed two-pass algorithm discovery via program crossover.

Search partial extrema reducers, then graft independently generated count
algorithms via AST alpha-renaming. No universal or SOTA claim; independently
check each composed candidate against held-out oracles. Stdlib Python 3.10+.
"""
from __future__ import annotations
import argparse
import json
import random
from dataclasses import dataclass, replace
from itertools import product
from algorithm_genome_v30 import (Expr, Stmt, Genome, Machine, InvalidGenome,
    FuelExhausted, atom, integer, op, type_check, to_dict, discover)
from genome_evolution_v31 import evolve


def rename_expr(expr: Expr, names: dict[str, str]) -> Expr:
    if expr.op == 'var':
        return replace(expr, value=names.get(expr.value, expr.value))
    return replace(expr, args=tuple(rename_expr(a, names) for a in expr.args))


def rename_stmt(stmt: Stmt, names: dict[str, str]) -> Stmt:
    return replace(stmt, name=names.get(stmt.name, stmt.name),
                   expr=rename_expr(stmt.expr, names) if stmt.expr is not None else None,
                   cond=rename_expr(stmt.cond, names) if stmt.cond is not None else None,
                   stop_if=rename_expr(stmt.stop_if, names) if stmt.stop_if is not None else None,
                   other=rename_expr(stmt.other, names) if stmt.other is not None else None,
                   then=tuple(rename_stmt(s, names) for s in stmt.then),
                   otherwise=tuple(rename_stmt(s, names) for s in stmt.otherwise))


def crossover(first: Genome, second: Genome, *, renames: dict[str, str]) -> Genome:
    """Typed program concatenation with capture-avoiding register renaming.

    Correctness of composition is NOT assumed: the independent target oracle
    evaluates every resulting program. Both parents are type checked first.
    """
    type_check(first)
    type_check(second)
    if not isinstance(renames, dict) or any(
            type(k) is not str or type(v) is not str for k, v in renames.items()):
        raise InvalidGenome('invalid register renaming')
    occupied = {name for name, _, _ in first.registers}
    entries = []
    for name, sort, initializer in second.registers:
        new = renames.get(name, name)
        if new in occupied or new in ('key', 'item', 'index', 'length'):
            raise InvalidGenome('register collision in crossover')
        occupied.add(new)
        entries.append((new, sort, rename_expr(initializer, renames)))
    combined = Genome(first.registers + tuple(entries),
                      first.statements + tuple(rename_stmt(s, renames) for s in second.statements),
                      rename_expr(second.result, renames), second.output_type)
    type_check(combined)
    return combined


def _prefix_grammar():
    index, item, best = atom('index'), atom('item'), atom('best')
    firsts = (op('eq', index, integer(0)),
              op('eq', index, op('sub', atom('length'), integer(1))))
    conditions = []
    for first in firsts:
        conditions.append(first)
        for compare in (op('lt', best, item), op('lt', item, best), op('eq', item, best)):
            conditions.extend((compare, op('or', first, compare), op('and', first, compare)))
    # 408 unseeded candidates: independently vary initialization,
    # condition, update expression and scan direction.
    for initial, condition, written, reverse in product(
            (integer(0), integer(1), integer(-1)),
            tuple(dict.fromkeys(conditions)),
            (atom('item'), atom('key'), integer(0), atom('best')),
            (False, True)):
        yield Genome((('best', 'int', initial),),
                     (Stmt('foreach', reverse=reverse,
                           then=(Stmt('if', cond=condition,
                                     then=(Stmt('set', name='best', expr=written),)),)),),
                     atom('best'), 'int')


def _partial_oracle(mode, values):
    if not values:
        return 0
    return max(values) if mode == 'max' else min(values)


def discover_prefix(mode):
    """Compositional partial synthesis: 781 binary-ish small arrays plus probes."""
    if mode not in ('max', 'min'):
        raise ValueError('mode must be max or min')
    vm = Machine()
    training = tuple(v for n in range(5)
                     for v in product((-2, -1, 0, 1, 2), repeat=n))
    probes = ((-2,), (2,), (-2, -1), (2, -1), (-2, 2),
              (2, -2), (-2, -2), (2, 2), (-2, 0, -1), (2, 0, 1))
    correct = []
    proposed = 0
    for program in _prefix_grammar():
        proposed += 1
        try:
            if any(vm.run(program, v, 0).value != _partial_oracle(mode, v)
                   for v in probes):
                continue
            if any(vm.run(program, v, 0).value != _partial_oracle(mode, v)
                   for v in training):
                continue
            correct.append(program)
        except (IndexError, InvalidGenome, FuelExhausted):
            continue
    if not correct:
        raise AssertionError('bounded grammar could not synthesize partial reducer')
    evaluation = ((-9, 4, 2, 8, -100), (0,) * 8,
                  tuple(range(17)), tuple(range(17, 0, -1)))
    def cost(candidate):
        executed = [vm.run(candidate, values, 0) for values in evaluation]
        return (sum(r.comparisons for r in executed),
                sum(r.steps for r in executed), candidate.nodes(),
                repr(to_dict(candidate)))
    return min(correct, key=cost), proposed, len(correct)


def _task_oracle(task, values):
    if task not in ('count_max', 'count_min', 'sum_max', 'sum_min'):
        raise ValueError('unsupported task')
    if not values:
        return 0
    extreme = max(values) if task.endswith('max') else min(values)
    return sum((1 if task.startswith('count') else value)
               for value in values if value == extreme)


def _cases(seed):
    # Training, validation, optimization and withheld measurement are disjoint.
    training = tuple((v, 0) for n in range(5)
                     for v in product((-2, -1, 0, 1, 2), repeat=n))
    fitness = tuple((tuple([1] * n + [-6 if negative else 9]), 0)
                    for n in (4, 8, 16, 32, 64) for negative in (True, False))
    fitness += tuple((tuple((j % 7) - 3 for j in range(n)), 0)
                     for n in (5, 10, 20, 40, 80))
    rng = random.Random(seed)
    validation = tuple((tuple(rng.randint(-30, 30) for _ in range(n)), 0)
                       for n in (0, 1, 2, 4, 8, 16, 64, 128) for _ in range(4))
    # Preserve four truly disjoint sets, including empty-array duplicate cases.
    seen_validation = set(training) | set(fitness)
    distinct_validation = []
    for values, key in validation:
        while (values, key) in seen_validation:
            values = tuple(v + 2**80 for v in values)
            key += 2**80
        seen_validation.add((values, key))
        distinct_validation.append((values, key))
    validation = tuple(distinct_validation)
    rng = random.Random(seed + 10319)
    hold = tuple((tuple(rng.randint(-10**12, 10**12) for _ in range(n)), 0)
                 for n in (0, 1, 2, 4, 8, 16, 64, 128) for _ in range(4))
    hold += tuple(((k,) * n, 0) for n in (1, 2, 16, 64, 128)
                  for k in (-10**19, 0, 10**19))
    hold += tuple((tuple(range(n)), 0) for n in (1, 16, 64, 128))
    used = set(training) | set(fitness) | set(validation)
    separated = []
    for values, key in hold:
        while (values, key) in used:
            values = tuple(v + 2**90 for v in values)
            key += 2**90  # also changes the empty-array case!
        separated.append((values, key))
        used.add((values, key))
    return training, validation, fitness, tuple(separated)


def _sum_parent(source: Genome) -> Genome:
    """Algebraic graft: conditionally add current item instead of +1.

    Count parents come from v3.0 and v3.1, not a prewritten sum-of-max
    implementation. The complete child must pass the independent oracle.
    """
    def alter(stmt):
        if stmt.op == 'set' and stmt.name == 'acc' and stmt.expr is not None:
            expr = stmt.expr
            if expr.op == 'add' and len(expr.args) == 2 and expr.args[0] == atom('acc'):
                if expr.args[1] == integer(1):
                    return replace(stmt, expr=op('add', atom('acc'), atom('item')))
                if expr.args[1].op == 'btoi' and len(expr.args[1].args) == 1:
                    cond = expr.args[1].args[0]
                    return Stmt('if', cond=cond, then=(
                        Stmt('set', name='acc', expr=op('add', atom('acc'), atom('item'))),))
        return replace(stmt, then=tuple(alter(s) for s in stmt.then),
                       otherwise=tuple(alter(s) for s in stmt.otherwise))
    return replace(source, statements=tuple(alter(s) for s in source.statements))


def _metrics(vm, program, cases):
    values = [vm.run(program, inp, key) for inp, key in cases]
    n = len(values)
    return (sum(x.comparisons for x in values) / n,
            sum(x.steps for x in values) / n,
            sum(x.writes for x in values) / n)


def _dominates(a, b):
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def _independent_one_pass_reference(task, cases):
    """Standalone correctness-checked one-pass baseline; never in search."""
    comparisons = 0
    for values, _ in cases:
        if not values:
            assert _task_oracle(task, values) == 0
            continue
        best = values[0]
        answer = 1 if task.startswith('count') else values[0]
        for value in values[1:]:
            comparisons += 1
            better = value > best if task.endswith('max') else value < best
            if better:
                best = value
                answer = 1 if task.startswith('count') else value
            else:
                comparisons += 1
                if value == best:
                    answer += 1 if task.startswith('count') else value
        if answer != _task_oracle(task, values):
            raise AssertionError('one-pass reference failed independent oracle')
    return comparisons / len(cases)


@dataclass(frozen=True)
class CompositionResult:
    task: str
    genome: Genome
    prefix_candidates: int
    verified_prefixes: int
    accepted_compositions: int
    pareto_points: int
    parent_names: tuple[str, ...]
    fitness: tuple[float, float, float]
    heldout: tuple[float, float, float]
    heldout_cases: int
    scalar_reference_comparisons: float
    status: str

    def report(self):
        return {'task': self.task, 'status': self.status,
                'prefix_candidates': self.prefix_candidates,
                'verified_prefixes': self.verified_prefixes,
                'accepted_compositions': self.accepted_compositions,
                'pareto_points': self.pareto_points, 'parents': list(self.parent_names),
                'fitness': list(self.fitness), 'heldout': list(self.heldout),
                'heldout_cases': self.heldout_cases,
                'one_pass_reference_comparisons': self.scalar_reference_comparisons,
                'genome': to_dict(self.genome), 'universal_correctness_proved': False,
                'novel_algorithm_claim': False, 'global_sota_claim': False}


def discover_composition(task='count_max', *, seed=3201):
    if task not in ('count_max', 'count_min', 'sum_max', 'sum_min') or type(seed) is not int:
        raise ValueError('invalid composition task or seed')
    mode = 'max' if task.endswith('max') else 'min'
    prefix, proposed, correct = discover_prefix(mode)
    training, validation, fitness, heldout = _cases(seed)
    vm = Machine(max_array=128)
    parents = (('enumerated-count', discover('count').genome),
               ('evolved-count', evolve('count').genome))
    pool = []
    encountered = set()
    for source_name, parent in parents:
        if task.startswith('sum'):
            parent = _sum_parent(parent)
        for reverse in (False, True):
            for stage in (prefix, replace(prefix, statements=(
                    replace(prefix.statements[0], reverse=reverse),))):
                program = crossover(stage, parent, renames={'acc': 'frequency', 'key': 'best'})
                if program in encountered:
                    continue
                encountered.add(program)
                try:
                    if any(vm.run(program, inp, key).value != _task_oracle(task, inp)
                           for inp, key in training):
                        continue
                    if any(vm.run(program, inp, key).value != _task_oracle(task, inp)
                           for inp, key in validation):
                        continue
                    score = _metrics(vm, program, fitness)
                    pool.append((score, program, source_name))
                except (InvalidGenome, FuelExhausted, IndexError):
                    continue
    if not pool:
        raise AssertionError('no valid crossover found in bounded grammar')
    frontier = [entry for entry in pool if not any(
        _dominates(other[0], entry[0]) for other in pool)]
    best = min(frontier, key=lambda x: (x[0], x[1].nodes(), repr(to_dict(x[1]))))
    program = best[1]
    for inp, key in heldout:
        output = vm.run(program, inp, key)
        if output.value != _task_oracle(task, inp) or output.final_array != inp:
            raise AssertionError('independent held-out correctness failure')
    return CompositionResult(task, program, proposed, correct, len(pool), len(frontier),
                             tuple(sorted({x[2] for x in pool})), best[0],
                             _metrics(vm, program, heldout), len(heldout),
                             _independent_one_pass_reference(task, heldout),
                             'empirically_validated')


def main():
    parser = argparse.ArgumentParser(description='Bounded two-pass typed genome crossover')
    parser.add_argument('--task', choices=('count_max', 'count_min', 'sum_max', 'sum_min'),
                        default='count_max')
    parser.add_argument('--output')
    args = parser.parse_args()
    result = discover_composition(args.task).report()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(payload + '\n', encoding='utf-8')
    print(payload)


if __name__ == '__main__':
    main()
