# AlgoGenesis v2.9 — Return to Algorithm Discovery

**Objective.** Recenter the repository on the **generation, independent
validation, and measurable improvement of executable algorithms**. SyGuS
remains as a supporting synthesis/verification subsystem, not the project's
primary objective.

**Repository base:** v2.8 merge `48ffdedc319342e414da0dad350bd44b01692fd0`.
**Domain for this first reboot milestone:** fixed-size sorting networks.
**Claim:** an unseeded grammar-based algorithm generator rediscovers
parallel sorting networks that improve on a specified repository baseline.
**Not claimed:** a mathematically new sorting algorithm, optimality proved
by our search, general-purpose algorithm invention, or global SOTA.

## Problem contract

Inputs: `width` wires over an arbitrary totally ordered domain.
Output: a **staged comparator network**, with each stage containing
disjoint pairs of wires. Each compare-exchange sends min to the lower
wire and max to the higher wire.

Objectives, lexicographically:
1. Sort **all** inputs, not only selected examples.
2. Use at most `max_stages` parallel compare-exchange rounds.
3. At a given reached depth, prefer fewer comparators.

The algorithm is `algorithm_invention_v29.invent`: it enumerates the
grammar of all nonempty disjoint comparator matchings on 2–8 wires,
searches stage sequences starting from the *empty identity network*,
and deduplicates by the full bit-parallel semantic output state.
Beam pruning uses the number of failing binary input patterns and
the candidate comparator count. It has explicit stage, comparator,
beam, and evaluation budgets. Candidate topologies are found by search,
not read from a task-specific lookup table or seeded into the pool.

### Correctness obligations

- Every stage has mutually disjoint, in-range comparator pairs.
- Stage flattening preserves sequential comparator semantics because
  pairs within a stage operate on disjoint wires.
- The bit-parallel oracle checks all `2**width` binary inputs against
  the sorted target.
- A **separate scalar interpreter** enumerates the same binary domain,
  comparing output with Python `sorted` instead of the bit-parallel
  target construction.
- The zero-one principle extends this exhaustive binary result to
  all totally ordered input values for that fixed width. This is
  correctness of the *produced network*, not a global optimality proof.
- Additional independent permutation checks and randomized large
  signed-integer tests are in `tests/test_algorithm_invention_v29.py`.
- Mutation tests remove a comparator and require actual failure,
  demonstrating that a verification gate rejects broken candidates.
- No result is returned as verified if the search budget is exhausted.

## Baselines and falsifiable target

| Width | Baseline (repository bubble network) | v2.9 target |
| --- | --- | --- |
| 5 | 10 comparators / scheduled depth 7 | 9 comparators / 5 stages |
| 6 | 15 comparators / scheduled depth 9 | 12 comparators / 5 stages |

The prior `advanced.prefix_beam` searches **one comparator at a time**.
The new implementation searches **disjoint comparator stages** and
measures depth as a primary resource. A separate regression test
compares the discovered width-6 candidate's scheduled depth to the
existing prefix-beam output under explicitly fixed search budgets.

These small-width comparator counts and depths are established prior
art. In particular, size 9/depth 5 for five inputs, and size 12/depth 5
for six inputs are known. This work is about adding the GENERATOR, not
claiming a newly invented network or a competitive search algorithm.
Relevant references:
- José A. R. Fonollosa (2018), *Joint Size and Depth Optimization of
  Sorting Networks*, https://arxiv.org/abs/1806.00305
- https://bertdobbelaere.github.io/sorting_networks.html
- Codish et al. (2016), *Sorting nine inputs requires twenty-five
  comparisons*, JCSS 82(3), pp. 551–563,
  https://doi.org/10.1016/j.jcss.2015.11.014

## Reproduce

    python -m unittest discover -s tests -v
    python algorithm_invention_v29.py --width 5 --stages 5 --comparators 9 --beam 256
    python algorithm_invention_v29.py --width 6 --stages 5 --comparators 12 --beam 256 --output invention_v29_width6.json

The v2.9 GitHub CI executes the width-6 generator and independently
checks the result. It uploads raw JSON with stage composition,
both oracle results, budget, and baseline metrics.

## Known limitations, threat model and next research gate

1. Width-2..8 stage enumeration is bounded; no proof of exhaustive
   global search follows from a beam-limited run.
2. One selected grammar family is insufficient for **general**
   autonomous algorithm invention. Next gate: typed algorithm IR,
   variable-length loops, recurrences and controlled data structures,
   semantics-preserving mutations and full benchmark isolation.
3. Semantic fitness and the bit-parallel oracle share a representation.
   The scalar checker and permutation tests provide a separate
   evaluation path, but the mathematical zero-one principle is common.
4. Small sorting networks are solved prior art. Claim only a concrete
   implementation improvement over the specified baselines.
5. Running generated networks in Python is not evidence of wall-clock
   throughput superiority: comparator count and dependency depth are
   modeled operations, not measured hardware latency.
6. Novelty must be screened separately before claiming a previously
   unknown algorithm. A later campaign should attempt **held-out,
   blinded algorithm families** and retain negative results.

**Acceptance criteria:** both CI jobs pass, search generates a
zero-error size-12/depth-5 six-wire network without seeded solutions,
independent scalar oracle and permutation tests pass, measured
comparison/depth savings against bubble remain positive, and the
prior search baseline comparison is explicit. Do not merge on a
failed or unexecuted acceptance gate.
