"""AlgoGenesis: bounded synthesis, canonicalization, and independent evaluation."""
from __future__ import annotations
import argparse
import json
import random
from dataclasses import dataclass
from discovery import binary_state, target_state, errors_from_state, apply_state, verify, all_pairs

def prune(network, width):
    """Remove redundant comparators without changing the full binary truth table."""
    seq = list(network)
    desired = binary_state(tuple(seq), width)
    i = len(seq)-1
    while i >= 0:
        trial = tuple(seq[:i] + seq[i+1:])
        if binary_state(trial, width) == desired:
            seq.pop(i)
        i -= 1
    return tuple(seq)

def counterexample(network, width):
    """Independent scalar oracle; return an input that is incorrectly sorted."""
    from algogenesis import run
    for mask in range(1 << width):
        values = [(mask >> i) & 1 for i in range(width)]
        if run(network, values) != sorted(values):
            return values
    return None

def prefix_beam(width, depth, beam=512, seed=0):
    """Beam search over semantic states, never seeded with a known network."""
    if not 2 <= width <= 10 or depth < 0 or beam < 1:
        raise ValueError('invalid beam search parameters')
    target = target_state(width)
    initial = binary_state((), width)
    frontier = {initial: ()}
    visited = {initial: 0}
    rng = random.Random(seed)
    pairs = list(all_pairs(width))
    for level in range(depth+1):
        solutions = [net for state,net in frontier.items() if state == target]
        if solutions:
            return min(solutions, key=lambda n: (len(n), n))
        if level == depth:
            break
        candidates = {}
        rng.shuffle(pairs)
        for state, net in frontier.items():
            for pair in pairs:
                nxt = apply_state(state, pair)
                if nxt == state or visited.get(nxt, depth+1) <= level+1:
                    continue
                cand = net + (pair,)
                if nxt not in candidates or cand < candidates[nxt]:
                    candidates[nxt] = cand
        ranked = sorted(candidates.items(), key=lambda item: (errors_from_state(item[0], target), item[1]))
        frontier = dict(ranked[:beam])
        for state in frontier:
            visited[state] = level+1
        if not frontier:
            break
    return None

@dataclass(frozen=True)
class Trial:
    seed: int
    found: bool
    comparators: int | None
    errors: int | None
    evaluations: int

def benchmark(width=4, seeds=range(10), generations=500, population=96):
    """Repeated independent evolutionary trials with no baseline seeding."""
    from discovery import discover
    results = []
    for seed in seeds:
        d = discover(width, generations, population, int(seed))
        results.append(Trial(int(seed), d.errors == 0, len(d.network), d.errors, d.evaluations))
    return {'width':width, 'trials':len(results), 'successes':sum(t.found for t in results),
            'results':[t.__dict__ for t in results]}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mode', choices=['beam','benchmark','verify'], default='beam')
    p.add_argument('--width',type=int,default=4)
    p.add_argument('--depth',type=int,default=6)
    p.add_argument('--beam',type=int,default=1024)
    p.add_argument('--trials',type=int,default=10)
    p.add_argument('--generations',type=int,default=500)
    p.add_argument('--population',type=int,default=96)
    p.add_argument('--seed',type=int,default=0)
    p.add_argument('--network',type=str,default='[]')
    args=p.parse_args()
    if args.mode=='beam':
        net=prefix_beam(args.width,args.depth,args.beam,args.seed)
        output={'found':net is not None,'network':net,'verification':verify(net,args.width) if net is not None else None}
    elif args.mode=='benchmark':
        output=benchmark(args.width,range(args.seed,args.seed+args.trials),args.generations,args.population)
    else:
        net=tuple(tuple(x) for x in json.loads(args.network))
        output={'verification':verify(net,args.width),'counterexample':counterexample(net,args.width), 'pruned':prune(net,args.width)}
    print(json.dumps(output,indent=2))

if __name__=='__main__':
    main()
