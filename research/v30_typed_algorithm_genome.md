# AlgoGenesis v3.0 — Typed Algorithm Genome Substrate

Base: merged v2.9 commit \`b9be24d317444e733898cf7e9ddcf4f26395b305\`.

## Objective and scope

This stage moves beyond fixed comparator networks into a **shared typed
program representation** capable of constructing and executing multiple
array algorithms, without seeding entire target programs. This is a
bounded, deterministic *foundation* for algorithm invention, **not** a
general algorithm invention system, a new algorithmic discovery, or SOTA.

The former SyGuS and sorting-network engines remain intact. The new
\`algorithm_genome_v30.py\` is independent of those benchmark names.

## Genome and execution contract

- Expressions are immutable typed ASTs with \`int\`, \`bool\`, variables,
  array \`read\`, integer \`add/sub\`, \`eq/lt\`, Boolean \`and/or/not\`,
  and explicit Boolean-to-integer conversion.
- Statements represent \`set\` (mutable typed registers), \`if\` (two
  branches), \`foreach\` (forward or reverse, optionally early-exiting),
  array \`store\`, and array \`swap\`. Nested loops are deliberately
  rejected by the current static checker.
- Register declarations and result sort are type checked. The interpreter
  accepts an array of integers and an integer key, copies the input
  array, applies bounded execution fuel and array-length limits, and
  returns the scalar result, final array, number of value comparisons,
  array writes, and executed VM steps.
- No arbitrary Python \`exec/eval\`, dynamic code import, I/O, external
  calls, or unbounded user-input loop execution. Array bounds are checked.
  Generated programs cannot bypass the static checker.
- The typed genome can express more programs than the **current generator
  enumerates**. This separation is intentional.

## Search, falsification and evaluation design

\`genome_candidates(task)\` composes expression and control-flow grammar
choices. It does not contain complete solutions or look up benchmark
program names. Four application contracts share the same typed interpreter:

| Task | Return/output | Search objective |
| --- | --- | --- |
| \`contains\` | Boolean membership result | Minimize equality/ordering comparisons |
| \`count\` | Number of equal elements | Minimize value comparisons |
| \`sum\` | Sum of array elements | Minimize comparisons (typically zero) |
| \`clamp\` | Array with negatives replaced by zero | Minimize writes to the array |

Four distinct data partitions:

1. **Training:** exhaustively enumerate arrays of length 0–4 and entries
   from {-1,0,1}, with keys from the same set. This is a **finite**
   363-input specification, not proof for arrays of arbitrary length.
2. **Search validation:** 51 deterministic larger, signed,
   duplicate-containing, empty and missing-key cases.
3. **Fitness:** 15 fixed early-hit, late-hit and absent-key cases.
   Value-comparison costs for scalar tasks and write counts for array
   transformation are computed **only on this selection corpus**.
4. **Withheld evaluation:** 51 independent cases with a separate RNG
   seed, integer range and edge-case patterns. This corpus is not used
   to choose, rank or filter candidates. The candidate is rejected if
   any withheld correctness check fails. Only after selection do we
   report held-out operation counts.

Independent oracles use Python built-in \`key in values\`,
\`tuple.count\`, \`sum\`, and a transformation built from \`max(0,x)\`.
These do not reuse the genome interpreter's expression evaluation.

**Statuses:** \`empirically_validated\`, \`not_found_in_bounds\`,
\`heldout_failed\`. A negative search result does NOT mean that no
valid algorithm exists. No current result claims an unbounded formal
proof, global optimality, or wall-clock superiority.

## Operation baselines and tradeoffs

\`contains\` is measured against an unconditional full array scan, one
equality per element. The generated early-termination strategy can
save comparisons on present-key workloads; misses still scan all
elements.

\`count\` uses a full array scan, one equality per element. Correct
counting in this grammar needs to inspect all values; the engine is
expected **not** to claim a comparison speedup.

\`sum\` uses no equality comparisons, so both candidate and appropriate
summation baseline have zero comparisons. No advantage is claimed.

\`clamp\` compares against a naive unconditional full-array write
baseline. The generated guarded-store algorithm writes only for
negative entries, but adds one comparison per element. Thus
**reduced memory writes are not proof of reduced latency**; relative
hardware costs and distribution matter.

\`Machine.steps\` measures modeled interpreter operations and is not
a timer or a direct CPU-cycle counter.

## Reproduce

    python -m unittest discover -s tests -v
    python algorithm_genome_v30.py --task contains --output v30_contains.json
    python algorithm_genome_v30.py --task count --output v30_count.json
    python algorithm_genome_v30.py --task sum --output v30_sum.json
    python algorithm_genome_v30.py --task clamp --output v30_clamp.json

GitHub CI must pass Python 3.10 and 3.13 suites, generate all four
artifacts on Python 3.13, and retain the v2.8 verified SyGuS plus
v2.9 sorting-network regression gates. The research evidence artifacts
are raw JSON produced by the same reproducible commands.

## Independent adversarial tests

- Reject ill-typed assignments and expressions, invalid names and
  unsupported/nested loops.
- Test read/write/swap behavior, empty arrays, negative values, input
  nonmutation, bounds errors and fuel exhaustion.
- Falsify an early-break mutation with a key appearing late.
- Test large signed values, duplicates and arrays of length 128
  against independent Python oracles.
- Repeat the candidate search to check determinism; run a strict
  budget of one candidate to prove it does not forge success.

## Next frontier

This milestone is a **typed algorithm genome kernel**, not an open-ended
invention agent. Next: grammar-directed structural mutations of whole
programs, variable-length multi-loop programs, explicit multiple
register dependencies, stronger semantic deduplication, real
Pareto analysis of time/space/branch/writes, independent hardware
timings, and a blinded multi-domain corpus. Prior-art comparison
must precede every novelty or SOTA claim.
