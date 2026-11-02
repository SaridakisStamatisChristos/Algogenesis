"""AlgoGenesis v0.1: reproducible evolutionary sorting-network discovery."""
from __future__ import annotations
import argparse
import itertools
import json
import random
from dataclasses import dataclass

Comparator = tuple[int, int]
Network = tuple[Comparator, ...]

def run(network: Network, values):
    a = list(values)
    for i, j in network:
        if a[i] > a[j]:
            a[i], a[j] = a[j], a[i]
    return a

def zero_one_errors(network: Network, n: int) -> int:
    """Zero-one principle: zero errors proves a fixed comparator network sorts all total orders."""
    return sum(run(network, bits) != sorted(bits)
               for bits in itertools.product((0, 1), repeat=n))

def bubble_network(n: int) -> Network:
    return tuple((j, j + 1) for i in range(n - 1) for j in range(n - 1 - i))

def all_pairs(n: int):
    return tuple(itertools.combinations(range(n), 2))

def mutate(net: Network, n: int, rng: random.Random) -> Network:
    pairs = all_pairs(n)
    seq = list(net)
    op = rng.choice(('insert', 'remove', 'replace', 'swap'))
    if op == 'insert' or not seq:
        seq.insert(rng.randrange(len(seq) + 1), rng.choice(pairs))
    elif op == 'remove':
        seq.pop(rng.randrange(len(seq)))
    elif op == 'replace':
        seq[rng.randrange(len(seq))] = rng.choice(pairs)
    else:
        i, j = rng.randrange(len(seq)), rng.randrange(len(seq))
        seq[i], seq[j] = seq[j], seq[i]
    return tuple(seq)

def fitness(net: Network, n: int):
    errors = zero_one_errors(net, n)
    return (errors, len(net))

@dataclass(frozen=True)
class Result:
    width: int
    seed: int
    generations: int
    population: int
    best: Network
    errors: int
    baseline_comparators: int

    def as_dict(self):
        return {'width': self.width, 'seed': self.seed,
                'generations': self.generations, 'population': self.population,
                'comparators': len(self.best), 'baseline_comparators': self.baseline_comparators,
                'zero_one_errors': self.errors, 'verified': self.errors == 0,
                'network': [list(p) for p in self.best]}

def evolve(n=4, generations=200, population=64, seed=42):
    if not 2 <= n <= 10:
        raise ValueError('width must be between 2 and 10 for bounded exhaustive verification')
    if generations < 0 or population < 2:
        raise ValueError('generations must be >= 0 and population >= 2')
    rng = random.Random(seed)
    baseline = bubble_network(n)
    pool = [baseline]
    for _ in range(population - 1):
        candidate = baseline
        for _ in range(rng.randrange(1, n + 2)):
            candidate = mutate(candidate, n, rng)
        pool.append(candidate)
    cache = {}
    def score(net):
        if net not in cache:
            cache[net] = fitness(net, n)
        return cache[net]
    for _ in range(generations):
        pool = sorted(set(pool), key=lambda net: (score(net), net))[:population]
        elite = pool[:max(1, population // 4)]
        next_pool = list(elite)
        while len(next_pool) < population:
            parent = rng.choice(pool[:max(1, len(pool) // 2)])
            next_pool.append(mutate(parent, n, rng))
        pool = next_pool
    best = min(pool + [baseline], key=lambda net: (score(net), net))
    return Result(n, seed, generations, population, best, score(best)[0], len(baseline))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--width', type=int, default=4)
    parser.add_argument('--generations', type=int, default=200)
    parser.add_argument('--population', type=int, default=64)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    print(json.dumps(evolve(args.width, args.generations, args.population, args.seed).as_dict(), indent=2))

if __name__ == '__main__':
    main()
