# AlgoGenesis v3.3 — Head/Tail One-Pass Genome Synthesis

**Base:** merged v3.2 \`c98962981079cc4d33cc5ee0bd1f0b5bbde6c0d5\`.
**Objective:** close a falsifiable algorithmic-performance gap between
v3.2 fused extrema aggregators and a strong independently checked one-pass
reference, without memorizing four final programs.

## New computational capability

\`Stmt('foreach', start=1)\` extends the existing typed genome with a
checked, inclusive loop-start index, while \`start=0\` preserves all
existing code. Reverse iteration respects the same lower bound. The
static checker rejects invalid, noninteger (including Boolean) and
negative start values. There is no change to the VM's array input
typing, signed unbounded arithmetic, fuel budget, mutation model, or
nested-loop rejection.

\`genome_headtail_v33.py\` enumerates a **task-independent grammar**
containing:
- two alternatives for strict better-than comparisons;
- two syntactic equality orientations;
- three first-element accumulator seeds;
- four reset expressions;
- four accumulation expressions;
- two comparator orderings (better-first or equality-first);
- two loop directions.

This gives 768 candidate *program structures*. A candidate consists
of two integer registers, a guarded first-element initialization
(\`0 < length\`, then read element 0), and a tail loop from index 1.
The reset, addition, ordering and comparison direction are selected
by search, NOT looked up from the benchmark task name.

An independent output oracle supplies each task's objective
\`count_max\`, \`count_min\`, \`sum_max\`, or \`sum_min\`.
Synthesis uses early falsification probes, then **781 training arrays**,
**32 validation arrays**, and **15 separate fitness cases**. Only
the selected candidate is checked on **51 held-out cases** and
compared against the v3.2 fused genome and a distinct correct one-pass
reference. All four corpora originate in \`genome_crossover_v32._cases\`
and are pairwise disjoint. Withheld correctness and performance
measurements are not inputs to ranking.

## Algorithmic invariant (human-checkable argument)

The generated successful pattern has the following shape, where
\`better(x,b)\` is either \`x>b\` or \`x<b\`, and \`same(x,b)\`
is \`x=b\`:

1. If the input array is empty, return the initialized result zero.
2. Otherwise initialize \`best\` from the first element and
   \`frequency\` from a chosen first-element expression.
3. For subsequent elements, update the extreme and reset the
   accumulator when \`better\` holds; otherwise update the
   accumulator when \`same\` holds.
4. Return the accumulator.

For the correct choices of reset and additive expression, the
inductive invariant after each nonempty processed prefix is:
\`best\` equals that prefix's maximum/minimum, and
\`frequency\` equals either its extreme multiplicity or the
sum of occurrences of its extreme. For each new item, exactly
one of greater, equal or less holds. Updating the extreme resets
the accumulator to the new element's contribution; equality adds
that contribution; an inferior element changes neither.
This proves the *abstract recurrence* for all finite input arrays
under total integer ordering and unbounded integer arithmetic.
The engine does **not** currently machine-check that a selected
typed AST meets every premise of this proof. Its executable
correctness gate is finite-domain independent validation. Do not
label the generated program formally verified.

## Comparison policy

Assess both **value-comparison counts** and **VM steps**, without
equating these to native latency. The existing v3.2
\`fuse(task)\` is a primary generated-algorithm baseline.
The independently verified one-pass reference from
\`genome_crossover_v32\` is a second and stronger comparator.

Acceptance gate (all four tasks on the same 51 held-out cases):
- correctness against independent Python task oracles;
- fewer comparisons and fewer modeled VM steps than v3.2 fusion;
- comparisons at most 115% of the independently checked one-pass
  reference (the gate is conservative about workload variation);
- no SOTA, universal formal proof, native speed or novelty claim.

The grammar also searches **equality-first** branches. On
duplicate-heavy workloads, these may improve comparison counts
over better-first ordering, but such a gain is workload-dependent
and does not imply a better algorithm universally.

## Falsification and limitations

- Removing the first-element guard must fail on the empty array.
- Changing \`start=1\` to \`start=0\` must double-count a singleton.
- Negative, Boolean, fractional and oversized loop starts are
  rejected before execution.
- Huge signed values, duplicate-rich arrays, all permutations on
  small domains and input arrays up to 128 elements are tested.
- Reproduce identical seeds and confirm no candidate is declared
  found when the enumeration budget is insufficient.
- All prior v2.8–v3.2 integration and proof gates remain present.

The grammar is **family-specific**: it searches among head/tail
extrema aggregations, not novel arbitrary algorithms. The next
milestone should compile generated programs to native code under
safe integer-domain constraints and benchmark measured latency
against strong established alternatives on pinned hardware, with
repeated paired trials and a separate blinded workload.
