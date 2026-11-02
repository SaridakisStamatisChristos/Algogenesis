"""v3.0 typed algorithm genome: executable loops, branches, registers, arrays.

Bounded synthesis substrate, not a general algorithm inventor. Generated
programs have finite-domain + held-out evidence, NOT universal proofs.
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from itertools import product
from typing import Any
import argparse
import json
import random


class InvalidGenome(ValueError):
    pass


class FuelExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class Expr:
    op: str
    args: tuple['Expr', ...] = ()
    value: int | bool | str | None = None

    def nodes(self) -> int:
        return 1 + sum(a.nodes() for a in self.args)


@dataclass(frozen=True)
class Stmt:
    op: str
    name: str | None = None
    expr: Expr | None = None
    cond: Expr | None = None
    then: tuple['Stmt', ...] = ()
    otherwise: tuple['Stmt', ...] = ()
    reverse: bool = False
    stop_if: Expr | None = None
    other: Expr | None = None


@dataclass(frozen=True)
class Genome:
    registers: tuple[tuple[str, str, Expr], ...]
    statements: tuple[Stmt, ...]
    result: Expr
    output_type: str

    def nodes(self) -> int:
        def count_stmt(s: Stmt) -> int:
            return (1 + sum(e.nodes() for e in (s.expr, s.cond, s.stop_if, s.other) if e is not None)
                    + sum(count_stmt(t) for t in s.then + s.otherwise))
        return (1 + sum(e.nodes() for _, _, e in self.registers)
                + self.result.nodes() + sum(count_stmt(s) for s in self.statements))


def atom(name: str) -> Expr:
    return Expr('var', value=name)


def integer(value: int) -> Expr:
    return Expr('int', value=value)


def boolean(value: bool) -> Expr:
    return Expr('bool', value=value)


def op(name: str, *args: Expr) -> Expr:
    return Expr(name, tuple(args))


def infer(expr: Expr, env: dict[str, str]) -> str:
    if not isinstance(expr, Expr):
        raise InvalidGenome('malformed expression')
    if expr.op == 'int' and type(expr.value) is int and not expr.args:
        return 'int'
    if expr.op == 'bool' and type(expr.value) is bool and not expr.args:
        return 'bool'
    if expr.op == 'var' and type(expr.value) is str and not expr.args and expr.value in env:
        return env[expr.value]
    if expr.op == 'read' and len(expr.args) == 1 and infer(expr.args[0], env) == 'int':
        return 'int'
    signatures = {
        'add': (('int', 'int'), 'int'), 'sub': (('int', 'int'), 'int'),
        'eq': (('int', 'int'), 'bool'), 'lt': (('int', 'int'), 'bool'),
        'and': (('bool', 'bool'), 'bool'), 'or': (('bool', 'bool'), 'bool'),
        'not': (('bool',), 'bool'), 'btoi': (('bool',), 'int'),
    }
    if expr.op not in signatures:
        raise InvalidGenome('unknown expression operator')
    inputs, output = signatures[expr.op]
    if len(expr.args) != len(inputs) or tuple(infer(a, env) for a in expr.args) != inputs:
        raise InvalidGenome('ill-typed operator')
    return output


def type_check(program: Genome) -> None:
    """Fail-closed static typing. The single foreach level is intentional."""
    if not isinstance(program, Genome) or program.output_type not in ('int', 'bool'):
        raise InvalidGenome('invalid output sort')
    env = {'key': 'int', 'item': 'int', 'index': 'int', 'length': 'int'}
    for name, sort, value in program.registers:
        if not isinstance(name, str) or name in env or sort not in ('int', 'bool'):
            raise InvalidGenome('invalid register declaration')
        if infer(value, env) != sort:
            raise InvalidGenome('register initializer sort mismatch')
        env[name] = sort

    def verify_stmt(s: Stmt, inside_loop: bool) -> None:
        if not isinstance(s, Stmt):
            raise InvalidGenome('malformed statement')
        if s.op == 'set':
            if s.name not in env or s.name in ('key', 'item', 'index', 'length') or s.expr is None:
                raise InvalidGenome('invalid assignment target')
            if infer(s.expr, env) != env[s.name]:
                raise InvalidGenome('assignment type mismatch')
        elif s.op == 'if':
            if s.cond is None or infer(s.cond, env) != 'bool':
                raise InvalidGenome('if requires boolean condition')
            for child in s.then + s.otherwise:
                verify_stmt(child, inside_loop)
        elif s.op == 'foreach':
            if inside_loop:
                raise InvalidGenome('nested loops outside v3.0 bounded grammar')
            if s.stop_if is not None and infer(s.stop_if, env) != 'bool':
                raise InvalidGenome('stop condition must be Boolean')
            if not s.then:
                raise InvalidGenome('empty foreach body')
            for child in s.then:
                verify_stmt(child, True)
        elif s.op in ('store', 'swap'):
            if (s.expr is None or s.other is None or
                    infer(s.expr, env) != 'int' or infer(s.other, env) != 'int'):
                raise InvalidGenome('array operation requires integer indices/values')
        else:
            raise InvalidGenome('unsupported statement')
    for stmt in program.statements:
        verify_stmt(stmt, False)
    if infer(program.result, env) != program.output_type:
        raise InvalidGenome('result type mismatch')


@dataclass(frozen=True)
class Execution:
    value: int | bool
    final_array: tuple[int, ...]
    comparisons: int
    steps: int
    writes: int


class Machine:
    """Fuel-bounded interpreter. Array mutation is confined to a private copy."""
    def __init__(self, *, fuel: int = 20000, max_array: int = 128):
        if (type(fuel) is not int or fuel < 1 or type(max_array) is not int or
                not 0 <= max_array <= 100000):
            raise ValueError('invalid machine bounds')
        self.fuel = fuel
        self.max_array = max_array

    def run(self, genome: Genome, values: tuple[int, ...] | list[int],
            key: int) -> Execution:
        type_check(genome)
        if (type(key) is not int or type(values) not in (tuple, list) or
                len(values) > self.max_array or any(type(v) is not int for v in values)):
            raise ValueError('inputs require bounded array of ints and integer key')
        data = list(values)
        env: dict[str, Any] = {'key': key, 'item': 0, 'index': 0, 'length': len(data)}
        fuel = self.fuel
        comparisons = writes = 0

        def tick():
            nonlocal fuel
            fuel -= 1
            if fuel < 0:
                raise FuelExhausted('execution fuel exhausted')

        def evaluate(e: Expr):
            nonlocal comparisons
            tick()
            if e.op in ('int', 'bool'):
                return e.value
            if e.op == 'var':
                return env[e.value]
            if e.op == 'read':
                i = evaluate(e.args[0])
                if not 0 <= i < len(data):
                    raise IndexError('array read out of bounds')
                return data[i]
            if e.op == 'not':
                return not evaluate(e.args[0])
            if e.op == 'btoi':
                return int(evaluate(e.args[0]))
            if e.op == 'and':
                return evaluate(e.args[0]) and evaluate(e.args[1])
            if e.op == 'or':
                return evaluate(e.args[0]) or evaluate(e.args[1])
            left, right = evaluate(e.args[0]), evaluate(e.args[1])
            if e.op in ('eq', 'lt'):
                comparisons += 1
                return left == right if e.op == 'eq' else left < right
            if e.op == 'add':
                return left + right
            if e.op == 'sub':
                return left - right
            raise AssertionError('typing missed expression')

        for name, _, initial in genome.registers:
            env[name] = evaluate(initial)

        def execute(statements: tuple[Stmt, ...]) -> None:
            nonlocal writes
            for stmt in statements:
                tick()
                if stmt.op == 'set':
                    env[stmt.name] = evaluate(stmt.expr)
                elif stmt.op == 'if':
                    execute(stmt.then if evaluate(stmt.cond) else stmt.otherwise)
                elif stmt.op == 'foreach':
                    indices = (range(len(data) - 1, -1, -1) if stmt.reverse
                               else range(len(data)))
                    for index in indices:
                        tick()
                        env['index'], env['item'] = index, data[index]
                        execute(stmt.then)
                        if stmt.stop_if is not None and evaluate(stmt.stop_if):
                            break
                elif stmt.op in ('store', 'swap'):
                    i = evaluate(stmt.expr)
                    if not 0 <= i < len(data):
                        raise IndexError('array index out of bounds')
                    if stmt.op == 'store':
                        data[i] = evaluate(stmt.other)
                        writes += 1
                    else:
                        j = evaluate(stmt.other)
                        if not 0 <= j < len(data):
                            raise IndexError('array index out of bounds')
                        data[i], data[j] = data[j], data[i]
                        writes += 2
                else:
                    raise AssertionError('typing missed statement')
        execute(genome.statements)
        return Execution(evaluate(genome.result), tuple(data),
                         comparisons, self.fuel - fuel, writes)


def expression_grammar(register: str, sort: str) -> tuple[Expr, ...]:
    """Composable, typed expressions; no prebuilt benchmark programs."""
    item, key = atom('item'), atom('key')
    equality = op('eq', item, key)
    less = op('lt', item, key)
    bools = (boolean(False), boolean(True), equality, less, op('not', equality))
    ints = (integer(0), integer(1), integer(-1), item, key, atom('index'), atom('length'))
    if sort == 'bool':
        acc = atom(register)
        candidates = [acc, *bools]
        for a, b in product((acc, *bools), (acc, *bools)):
            candidates.extend((op('or', a, b), op('and', a, b)))
        return tuple(dict.fromkeys(candidates))
    if sort == 'int':
        acc = atom(register)
        conversion = [op('btoi', b) for b in bools]
        candidates = [acc, *ints, *conversion]
        for a, b in product((acc, integer(0), integer(1)),
                            (item, key, *conversion, integer(1))):
            candidates.extend((op('add', a, b), op('sub', a, b)))
        return tuple(dict.fromkeys(candidates))
    raise ValueError('unknown register sort')


def genome_candidates(task: str):
    """Generate programs by cross-product of typed expressions and flow control."""
    if task not in ('contains', 'count', 'sum', 'clamp'):
        raise ValueError('unsupported research task')
    if task == 'clamp':
        item = atom('item')
        conditions = (boolean(True), boolean(False), op('lt', item, integer(0)),
                      op('lt', integer(0), item), op('eq', item, integer(0)),
                      op('lt', item, atom('key')))
        values = (integer(0), integer(1), item, atom('key'), op('sub', item, item))
        for condition, value, reverse in product(conditions, values, (False, True)):
            action = Stmt('store', expr=atom('index'), other=value)
            branch = (Stmt('if', cond=condition, then=(action,)),)
            yield Genome((), (Stmt('foreach', then=branch, reverse=reverse),),
                         integer(0), 'int')
            yield Genome((), (Stmt('foreach', then=(action,), reverse=reverse),),
                         integer(0), 'int')
        return
    sort = 'bool' if task == 'contains' else 'int'
    init_values = (boolean(False), boolean(True)) if sort == 'bool' else (integer(0), integer(1))
    expressions = expression_grammar('acc', sort)
    tests = (expression_grammar('acc', 'bool') if sort == 'bool' else (
        op('eq', atom('item'), atom('key')),
        op('lt', atom('item'), atom('key')), boolean(True)))
    stops = (None, atom('acc'), op('eq', atom('item'), atom('key'))) if sort == 'bool' else (None,)
    for init in init_values:
        for expr in expressions:
            for reverse in (False, True):
                body = (Stmt('set', name='acc', expr=expr),)
                for stop in stops:
                    yield Genome((('acc', sort, init),),
                                 (Stmt('foreach', then=body, reverse=reverse, stop_if=stop),),
                                 atom('acc'), sort)
            for condition in tests[:5]:
                branch = (Stmt('if', cond=condition,
                               then=(Stmt('set', name='acc', expr=expr),)),)
                yield Genome((('acc', sort, init),),
                             (Stmt('foreach', then=branch),), atom('acc'), sort)


def oracle(task: str, values: tuple[int, ...], key: int):
    if task == 'contains':
        return key in values
    if task == 'count':
        return values.count(key)
    if task == 'sum':
        return sum(values)
    if task == 'clamp':
        return tuple(max(0, x) for x in values)
    raise ValueError('unknown task')


def all_training_cases():
    alphabet = (-1, 0, 1)
    for n in range(5):
        for values in product(alphabet, repeat=n):
            for key in alphabet:
                yield values, key


@dataclass(frozen=True)
class Discovery:
    task: str
    genome: Genome | None
    generated: int
    correct: int
    heldout: int
    mean_comparisons: float | None
    baseline_mean_comparisons: float
    mean_writes: float | None
    baseline_mean_writes: float
    status: str

    def report(self) -> dict:
        return {'task': self.task, 'status': self.status,
                'candidate_count': self.generated, 'correct_on_training': self.correct,
                'heldout_cases': self.heldout,
                'mean_comparisons': self.mean_comparisons,
                'baseline_mean_comparisons': self.baseline_mean_comparisons,
                'mean_array_writes': self.mean_writes,
                'baseline_mean_array_writes': self.baseline_mean_writes,
                'bounded_finite_validation_only': True,
                'genome': to_dict(self.genome) if self.genome is not None else None}


def to_dict(value):
    if isinstance(value, (Expr, Stmt, Genome)):
        return {field.name: to_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [to_dict(v) for v in value]
    return value


def discover(task: str = 'contains', *, limit: int = 10000, seed: int = 731) -> Discovery:
    """Finite CEGIS-style enumerator with disjoint search and evaluation sets.

    This is exhaustive evaluation of a finite input domain over a bounded
    constructed candidate grammar, not universal proof or optimality.
    """
    if type(limit) is not int or limit < 1 or type(seed) is not int:
        raise ValueError('invalid search arguments')
    cases = tuple(all_training_cases())
    rng = random.Random(seed)
    validation = [(tuple(rng.randint(-7, 7) for _ in range(n)), rng.randint(-7, 7))
                  for n in (0, 1, 2, 4, 8, 16, 32, 64) for _ in range(4)]
    validation.extend((tuple([key] * n), key) for n in (1, 2, 8, 32, 64)
                      for key in (-9, 0, 9))
    validation.extend((tuple(range(n)), n + 1) for n in (1, 8, 32, 64))
    # Truly held-out: generated from a different seed/range; not used for
    # candidate filtering, cost ranking or tie breaking.
    hold_rng = random.Random(seed + 1009)
    heldout = [(tuple(hold_rng.randint(-101, 101) for _ in range(n)),
                hold_rng.randint(-101, 101))
               for n in (0, 1, 2, 4, 8, 16, 32, 64) for _ in range(4)]
    heldout.extend((tuple([key] * n), key) for n in (1, 2, 8, 32, 64)
                   for key in (-93, 0, 93))
    heldout.extend((tuple(range(n)), n + 11) for n in (1, 8, 32, 64))
    # Optimization workload is separate from validation and held-out cases.
    cost_cases = (tuple(((-9,) + (1,) * n, -9) for n in (4, 8, 16, 32, 64))
                  + tuple(((1,) * n + (-9,), -9) for n in (4, 8, 16, 32, 64))
                  + tuple(((1,) * n, -9) for n in (4, 8, 16, 32, 64)))
    vm = Machine()
    avg_length = sum(len(v) for v, _ in heldout) / len(heldout)
    baseline = avg_length if task in ('contains', 'count') else 0.0
    baseline_writes = avg_length if task == 'clamp' else 0.0
    best = None
    best_score = None
    total = valid = 0
    for candidate in genome_candidates(task):
        if total >= limit:
            break
        total += 1
        try:
            type_check(candidate)
            def accepted(v, k):
                execution = vm.run(candidate, v, k)
                return (execution.final_array if task == 'clamp'
                        else execution.value) == oracle(task, v, k)
            if any(not accepted(v, k) for v, k in cases):
                continue
            if any(not accepted(v, k) for v, k in validation):
                continue
            valid += 1
            cost = sum((vm.run(candidate, v, k).writes if task == 'clamp'
                        else vm.run(candidate, v, k).comparisons)
                       for v, k in cost_cases) / len(cost_cases)
            score = (cost, candidate.nodes(), repr(to_dict(candidate)))
            if best_score is None or score < best_score:
                best, best_score = candidate, score
        except (InvalidGenome, FuelExhausted, IndexError):
            continue
    if best is not None:
        for v, k in heldout:
            execution = vm.run(best, v, k)
            actual = execution.final_array if task == 'clamp' else execution.value
            if actual != oracle(task, v, k):
                return Discovery(task, None, total, valid, len(heldout),
                                 None, baseline, None, baseline_writes,
                                 'heldout_failed')
    mean_comparisons = (sum(vm.run(best, v, k).comparisons for v, k in heldout) / len(heldout)
                        if best is not None else None)
    mean_writes = (sum(vm.run(best, v, k).writes for v, k in heldout) / len(heldout)
                   if best is not None else None)
    return Discovery(task, best, total, valid, len(heldout), mean_comparisons,
                     baseline, mean_writes, baseline_writes,
                     'empirically_validated' if best is not None else 'not_found_in_bounds')


def main():
    parser = argparse.ArgumentParser(description='AlgoGenesis v3.0 typed algorithm genome search')
    parser.add_argument('--task', choices=['contains', 'count', 'sum', 'clamp'], default='contains')
    parser.add_argument('--limit', type=int, default=10000)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = discover(args.task, limit=args.limit).report()
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(payload + '\n', encoding='utf-8')
    print(payload)
    if result['status'] != 'empirically_validated':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
