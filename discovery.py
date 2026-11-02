"""Independent zero-one verifier, unseeded evolution, and exact small-width search."""
from __future__ import annotations
import argparse
from collections import deque
from dataclasses import dataclass
import json
import random
from algogenesis import all_pairs, bubble_network

Network = tuple[tuple[int, int], ...]

def validate(network: Network, width: int) -> None:
    if not 2 <= width <= 12:
        raise ValueError('width must be in [2,12]')
    if any(not (0 <= i < j < width) for i, j in network):
        raise ValueError('invalid comparator')

def binary_state(network: Network, width: int) -> tuple[int, ...]:
    """Apply comparators to all 2**width binary inputs in bit-parallel form."""
    validate(network, width)
    wires = []
    for wire in range(width):
        pattern = 0
        for value in range(1 << width):
            if value & (1 << wire):
                pattern |= 1 << value
        wires.append(pattern)
    for i, j in network:
        a, b = wires[i], wires[j]
        wires[i] = a & b
        wires[j] = a | b
    return tuple(wires)

def target_state(width: int) -> tuple[int, ...]:
    return binary_state(bubble_network(width), width)

def errors_from_state(state: tuple[int, ...], target: tuple[int, ...]) -> int:
    """Number of input patterns with at least one wrong output wire."""
    mask = 0
    for a, b in zip(state, target):
        mask |= a ^ b
    return mask.bit_count()

def verify(network: Network, width: int) -> dict:
    actual = binary_state(network, width)
    expected = target_state(width)
    bad = errors_from_state(actual, expected)
    return {'width': width, 'comparators': len(network), 'errors': bad,
            'verified': bad == 0, 'method': 'exhaustive-zero-one-bitparallel'}

def apply_state(state: tuple[int, ...], pair: tuple[int, int]) -> tuple[int, ...]:
    i, j = pair
    result = list(state)
    result[i], result[j] = state[i] & state[j], state[i] | state[j]
    return tuple(result)

def exact_search(width: int, max_states: int = 500000) -> Network:
    """BFS over semantic states proves minimum comparator count for widths <= 4."""
    if not 2 <= width <= 4:
        raise ValueError('exact search supported for widths 2..4')
    start = binary_state((), width)
    target = target_state(width)
    queue = deque([start])
    parents = {start: None}
    pairs = all_pairs(width)
    while queue:
        state = queue.popleft()
        if state == target:
            result = []
            while parents[state] is not None:
                prev, pair = parents[state]
                result.append(pair)
                state = prev
            return tuple(reversed(result))
        for pair in pairs:
            nxt = apply_state(state, pair)
            if nxt not in parents:
                if len(parents) >= max_states:
                    raise RuntimeError('exact state budget exceeded')
                parents[nxt] = (state, pair)
                queue.append(nxt)
    raise RuntimeError('no solution')

def random_network(width: int, length: int, rng: random.Random) -> Network:
    pairs = all_pairs(width)
    return tuple(rng.choice(pairs) for _ in range(length))

def mutation(net: Network, width: int, rng: random.Random, max_length: int) -> Network:
    seq = list(net)
    ops = ['replace', 'swap']
    if len(seq) < max_length:
        ops.append('insert')
    if seq:
        ops.append('remove')
    op = rng.choice(ops)
    if op == 'insert':
        seq.insert(rng.randrange(len(seq) + 1), rng.choice(all_pairs(width)))
    elif op == 'remove':
        seq.pop(rng.randrange(len(seq)))
    elif op == 'replace':
        if seq:
            seq[rng.randrange(len(seq))] = rng.choice(all_pairs(width))
        else:
            seq.append(rng.choice(all_pairs(width)))
    elif op == 'swap' and len(seq) > 1:
        a, b = rng.sample(range(len(seq)), 2)
        seq[a], seq[b] = seq[b], seq[a]
    return tuple(seq)

@dataclass(frozen=True)
class Discovery:
    width: int
    seed: int
    generations: int
    population: int
    network: Network
    errors: int
    evaluations: int
    seeded_with_baseline: bool = False

    def as_dict(self):
        return {**verify(self.network, self.width), 'seed': self.seed,
                'generations': self.generations, 'population': self.population,
                'evaluations': self.evaluations, 'seeded_with_baseline': self.seeded_with_baseline,
                'network': [list(p) for p in self.network]}

def discover(width=4, generations=1000, population=128, seed=42, max_length=None) -> Discovery:
    """Unseeded evolutionary search; no known-correct networks in population."""
    if not 2 <= width <= 10 or generations < 0 or population < 2:
        raise ValueError('invalid search parameters')
    rng = random.Random(seed)
    cap = max_length if max_length is not None else width * (width - 1)
    if cap < 1:
        raise ValueError('max_length must be positive')
    target = target_state(width)
    pool = [random_network(width, rng.randrange(1, cap + 1), rng) for _ in range(population)]
    cache = {}
    def score(net):
        if net not in cache:
            cache[net] = (errors_from_state(binary_state(net, width), target), len(net))
        return cache[net]
    best = min(pool, key=lambda net: (score(net), net))
    for _ in range(generations):
        pool = sorted(set(pool), key=lambda net: (score(net), net))
        if (score(pool[0]), pool[0]) < (score(best), best):
            best = pool[0]
        elites = pool[:max(2, min(len(pool), population // 8))]
        next_pool = list(elites)
        while len(next_pool) < population:
            if rng.random() < 0.10:
                next_pool.append(random_network(width, rng.randrange(1, cap + 1), rng))
            else:
                next_pool.append(mutation(rng.choice(pool[:max(1, len(pool)//2)]), width, rng, cap))
        pool = next_pool
    candidate = min(pool, key=lambda net: (score(net), net))
    if (score(candidate), candidate) < (score(best), best):
        best = candidate
    return Discovery(width, seed, generations, population, best, score(best)[0], len(cache))

def main():
    p = argparse.ArgumentParser(description='AlgoGenesis independent discovery laboratory')
    p.add_argument('--mode', choices=['evolve', 'exact'], default='evolve')
    p.add_argument('--width', type=int, default=4)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--generations', type=int, default=1000)
    p.add_argument('--population', type=int, default=128)
    args = p.parse_args()
    if args.mode == 'exact':
        net = exact_search(args.width)
        output = {**verify(net, args.width), 'optimality': 'proved-by-exhaustive-semantic-BFS',
                  'network': [list(p) for p in net]}
    else:
        output = discover(args.width, args.generations, args.population, args.seed).as_dict()
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
