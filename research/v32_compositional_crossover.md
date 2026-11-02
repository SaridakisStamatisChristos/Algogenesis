# AlgoGenesis v3.2 — Compositional Crossover and Loop Fusion

**Base:** v3.1 merged at \`edec41c25f4c1f490da29a472c90ccdf4ac2cc93\`.
**Evidence level:** bounded finite-domain verification, not universal proof or SOTA.

## Mission

Extend v3.1 whole-program mutations to **independently synthesized
multi-register/two-pass algorithms**, generic AST crossover, and
automatically searched one-pass fusion. Earlier modules stay intact.

\`genome_crossover_v32.py\` enumerates **408** typed candidate extrema
reducers by independently varying initialization, conditions, assignment
values and loop direction. It checks partial programs against a small
falsification set and **781 exhaustive input arrays** (length 0–4,
entries in {-2,-1,0,1,2}). A verified prefix is grafted onto an actual
v3.0-generated or v3.1-evolved accumulator program. Capture-avoiding
alpha-renaming changes accumulator register \`acc\` to \`frequency\`,
and redirects the source \`key\` operand to the independently computed
\`best\` register, including through nested statements. Syntax and
register collisions are rejected.

The two-pass grammar covers four new tasks:
\`count_max\`, \`count_min\`, \`sum_max\`, \`sum_min\`. The sum variant
transforms the second parent's conditional \`+1\` increment into a
conditional \`+item\`. This is verified on the complete composed
program; the system is not handed a full solution table.

\`genome_fusion_v32.py\` derives a one-pass program by combining the
first loop's reducer updates and the second loop's accumulator updates,
searching four possible reset expressions. Only whole programs that
pass independent task oracles are retained.

## Search integrity

Four **pairwise-disjoint** sets under \`seed=3201\`:
1. Training: 781 exact small arrays.
2. Validation: 32 independently generated arrays, up to length 128.
3. Fitness: 15 fixed, non-held-out arrays, scoring modeled comparisons,
   VM steps, array writes in that order.
4. Held-out: 51 independent arrays, including extremes, all-equal,
   absent cases and arrays up to 128 entries. They are never used to
   select the final candidate, only to falsify and report its outcome.

Collisions are shifted without breaking the equality relationships,
including the empty-array case. A separate Python reference checks
each result using max/min and counting/summing matching elements.

An independently implemented, **correctness-checked** one-pass
max/min accumulator serves as a *strong comparator*. It is never fed
into synthesis. Only comparisons are measured across Python and the
typed VM; VM step counts cannot be equated to native runtime.

## Local evidence, withheld 51-case set

All figures are **mean modeled operation counts**, not measured latency.

| Task | Two-pass comparisons | Fused comparisons | Strong one-pass reference | Two-pass VM steps | Fused VM steps |
|---|---:|---:|---:|---:|---:|
| count_max | 101.08 | 94.82 | 60.82 | 542.90 | 491.71 |
| count_min | 101.08 | 99.29 | 65.29 | 533.96 | 491.71 |
| sum_max | 101.08 | 94.82 | 60.82 | 542.90 | 491.71 |
| sum_min | 101.08 | 99.29 | 65.29 | 533.96 | 491.71 |

Fusion improves both metrics against the actual generated two-pass
parent, but **all fused candidates lose badly to the strong one-pass
reference on comparison count**. This limits any SOTA claim.
No speedup or novel algorithm family has been proved.

## Independent tests

- Full typed AST crossover and nested alpha-renaming; reject register
  collisions, malformed mappings and unsupported tasks.
- Mutation falsification: remove the first pass, swap max/min, corrupt
  a fused reset; each produces an independently checked counterexample.
- Extensively compare all four tasks against Python task oracles,
  including arrays of length 0–128, huge signed values and duplicates.
- Assert disjoint evaluation sets and deterministic seeded synthesis.
- Verify that fused programs contain one loop and two state registers.
- Retain negative result: all fused programs still use more comparisons
  than the independently correct one-pass comparator.
- Preserve v2.8 SyGuS/Z3, v2.9 sorting and v3.0/3.1 genome gates.

## Reproduce

    python -m unittest discover -s tests -v
    python genome_crossover_v32.py --task count_max --output v32_two_count_max.json
    python genome_fusion_v32.py --task count_max --output v32_fused_count_max.json

Repeat for count_min, sum_max, sum_min. The CI job emits eight JSON
artifacts with the selected typed programs and full operation metrics.

## Next SOTA-directed frontier

Learn generic one-pass folds and inductive invariants without special
task hints; preserve counterexamples; expand to typed data structures
and mutation/crossover beyond extrema; compile programs for actual
wall-time benchmarks against strong established implementations.
Failure of finite synthesis is not unsatisfiability. Finite testing is
not a universal proof. Repeated reductions in VM operation counts are
not proof of hardware speedups or research novelty.
