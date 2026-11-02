"""v2.9: discover parallel sorting algorithms from a grammar of comparator stages.

A stage is a nonempty matching of input wires: all comparators in it are
disjoint and can execute concurrently. Search starts from the identity
network, never a supplied known solution. Semantic deduplication keeps the
least expensive candidate for each full Boolean-output state per depth.

The objective is lexicographic: zero incorrect Boolean inputs first,
then fewest comparators for a fixed maximum number of parallel stages.
The zero-one principle converts a complete 2**width Boolean verification
into correctness for arbitrary totally ordered inputs. This does NOT
prove global size/depth optimality; search is beam- and budget-bounded.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
import json

from algogenesis import all_pairs, bubble_network, run
from discovery import binary_state, target_state, errors_from_state, apply_state, verify

Comparator = tuple[int, int]
Stage = tuple[Comparator, ...]
Stages = tuple[Stage, ...]


@lru_cache(maxsize=None)
def matching_grammar(width: int) -> tuple[Stage, ...]:
    """All nonempty independent-comparator sets, independently of a solution."""
    if type(width) is not int or not 2 <= width <= 8:
        raise ValueError('stage search supports 2..8 wires')
    pairs = all_pairs(width)
    result: list[Stage] = []

    def build(index: int, occupied: int, stage: list[Comparator]) -> None:
        if index == len(pairs):
            if stage:
                result.append(tuple(stage))
            return
        a, b = pairs[index]
        build(index + 1, occupied, stage)
        if not (occupied & ((1 << a) | (1 << b))):
            stage.append((a, b))
            build(index + 1, occupied | (1 << a) | (1 << b), stage)
            stage.pop()

    build(0, 0, [])
    return tuple(sorted(result, key=lambda stage: (-len(stage), stage)))


def flatten(stages: Stages) -> tuple[Comparator, ...]:
    return tuple(pair for stage in stages for pair in stage)


def validate_stages(stages: Stages, width: int) -> None:
    if not isinstance(stages, tuple):
        raise ValueError('stages must be an immutable tuple')
    for stage in stages:
        if not isinstance(stage, tuple) or not stage:
            raise ValueError('each stage must be a nonempty tuple')
        occupied: set[int] = set()
        for pair in stage:
            if (not isinstance(pair, tuple) or len(pair) != 2 or
                    any(type(index) is not int for index in pair)):
                raise ValueError('invalid comparator')
            a, b = pair
            if not 0 <= a < b < width or a in occupied or b in occupied:
                raise ValueError('non-disjoint or out-of-range comparator')
            occupied.update((a, b))


def dependency_depth(network: tuple[Comparator, ...], width: int) -> int:
    """Earliest parallel schedule respecting all wire dependencies."""
    ready = [0] * width
    for a, b in network:
        if not (0 <= a < b < width):
            raise ValueError('invalid comparator')
        step = 1 + max(ready[a], ready[b])
        ready[a] = ready[b] = step
    return max(ready)


def scalar_certificate(stages: Stages, width: int) -> dict:
    """Independent ordinary Python comparator interpreter, not bit-parallel."""
    validate_stages(stages, width)
    network = flatten(stages)
    failures = []
    for mask in range(1 << width):
        values = tuple((mask >> i) & 1 for i in range(width))
        actual = run(network, values)
        if actual != sorted(values):
            failures.append(list(values))
    return {'checked_binary_inputs': 1 << width,
            'valid': not failures,
            'first_counterexample': failures[0] if failures else None}


@dataclass(frozen=True)
class Invention:
    width: int
    max_stages: int
    max_comparators: int
    beam: int
    stages: Stages | None
    evaluations: int
    depth_reached: int
    frontier_sizes: tuple[int, ...]
    best_errors: tuple[int, ...]
    status: str

    def report(self) -> dict:
        base = bubble_network(self.width)
        data = {
            'algorithm_family': 'parallel-oblivious-sorting-network',
            'search': 'unseeded-semantic-stage-beam',
            'width': self.width,
            'limits': {'stages': self.max_stages, 'comparators': self.max_comparators,
                       'beam': self.beam},
            'evaluations': self.evaluations,
            'frontier_sizes': list(self.frontier_sizes),
            'best_errors': list(self.best_errors),
            'status': self.status,
            'baseline': {'name': 'bubble_network', 'comparators': len(base),
                         'depth': dependency_depth(base, self.width)},
        }
        if self.stages is not None:
            net = flatten(self.stages)
            data['candidate'] = {
                'stages': [[list(pair) for pair in stage] for stage in self.stages],
                'network': [list(pair) for pair in net],
                'comparators': len(net), 'parallel_depth': len(self.stages),
                'scheduled_depth': dependency_depth(net, self.width),
                'bitparallel': verify(net, self.width),
                'independent_scalar': scalar_certificate(self.stages, self.width),
                'comparator_saving': len(base) - len(net),
                'depth_saving': dependency_depth(base, self.width) - len(self.stages),
                'global_optimality_proved': False,
                'novel_algorithm_claim': False,
            }
        return data


def invent(width: int = 6, *, max_stages: int = 5, max_comparators: int = 12,
           beam: int = 256, max_evaluations: int = 500000) -> Invention:
    if (type(width) is not int or not 2 <= width <= 8 or
            type(max_stages) is not int or not 1 <= max_stages <= 12 or
            type(max_comparators) is not int or not 1 <= max_comparators <= 60 or
            type(beam) is not int or not 1 <= beam <= 20000 or
            type(max_evaluations) is not int or
            not 1 <= max_evaluations <= 10000000):
        raise ValueError('invalid discovery bounds')
    target = target_state(width)
    initial = binary_state((), width)
    grammar = matching_grammar(width)
    frontier: dict[tuple[int, ...], tuple[int, Stages]] = {initial: (0, ())}
    evaluations = 0
    sizes: list[int] = []
    errors: list[int] = []

    def snapshot() -> None:
        sizes.append(len(frontier))
        errors.append(min(errors_from_state(s, target) for s in frontier))

    for depth in range(max_stages + 1):
        snapshot()
        solutions = [(cost, stages) for state, (cost, stages) in frontier.items()
                     if state == target and cost <= max_comparators]
        if solutions:
            cost, winner = min(solutions)
            validate_stages(winner, width)
            return Invention(width, max_stages, max_comparators, beam, winner,
                             evaluations, depth, tuple(sizes), tuple(errors), 'verified')
        if depth == max_stages:
            break
        next_states: dict[tuple[int, ...], tuple[int, Stages]] = {}
        for state, (cost, stages) in frontier.items():
            for stage in grammar:
                if evaluations >= max_evaluations:
                    return Invention(width, max_stages, max_comparators, beam, None,
                                     evaluations, depth, tuple(sizes), tuple(errors),
                                     'budget_exhausted')
                candidate_cost = cost + len(stage)
                if candidate_cost > max_comparators:
                    continue
                evaluations += 1
                next_state = state
                for pair in stage:
                    next_state = apply_state(next_state, pair)
                if next_state == state:
                    continue
                candidate = (candidate_cost, stages + (stage,))
                old = next_states.get(next_state)
                if old is None or candidate < old:
                    next_states[next_state] = candidate
        frontier = dict(sorted(
            next_states.items(),
            key=lambda item: (errors_from_state(item[0], target),
                              item[1][0], item[1][1])
        )[:beam])
        if not frontier:
            return Invention(width, max_stages, max_comparators, beam, None,
                             evaluations, depth + 1, tuple(sizes), tuple(errors),
                             'not_found_in_bounds')
    return Invention(width, max_stages, max_comparators, beam, None,
                     evaluations, max_stages, tuple(sizes), tuple(errors),
                     'not_found_in_bounds')


def main() -> None:
    parser = argparse.ArgumentParser(description='Discover parallel sorting-network algorithms')
    parser.add_argument('--width', type=int, default=6)
    parser.add_argument('--stages', type=int, default=5)
    parser.add_argument('--comparators', type=int, default=12)
    parser.add_argument('--beam', type=int, default=256)
    parser.add_argument('--max-evaluations', type=int, default=500000)
    parser.add_argument('--output', type=str)
    args = parser.parse_args()
    report = invent(args.width, max_stages=args.stages,
                    max_comparators=args.comparators, beam=args.beam,
                    max_evaluations=args.max_evaluations).report()
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(output + '\n', encoding='utf-8')
    print(output)
    if report['status'] != 'verified':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
