# AlgoGenesis v3.1 — Structural Evolution of Executable Algorithm Genomes

**Source baseline:** v3.0 merged \`fb48f5c5ddd7f9daafbde3d113d55a7248904559\`.
**Scope:** finite-domain algorithm improvement via typed AST mutations.
**Novelty:** existing compiler-style transformation mechanisms; no novel
mathematical algorithm or broader SOTA claim.

## Research contract

The v3.0 program generator constructs a well-typed initial genome for one
of four array-processing tasks. The **new v3.1 evolutionary layer** takes
that *generated program* and modifies its AST recursively. It does not
copy a prewritten improved program or search only a list of benchmark
solutions.

Structural operators include:
- numeric literals, variable references, comparison, Boolean and
  arithmetic operator substitutions;
- rewrite inside nested expression trees;
- typed register-initializer mutations;
- interchange a conditional's branches and negate its predicate;
- loop direction reversal and early-stop mutation;
- nested statement deletion/duplication;
- array-store value modifications; and
- conversion of a **Boolean-as-integer accumulator increment**
  into conditional control flow (and the inverse).

This last transformation has a simple algebraic proof. For arbitrary
integer register \`r\` and side-effect-free predicate \`P\`:

\[
r \leftarrow r + \mathrm{int}(P)
\quad\equiv\quad
\text{if }P\text{ then }r\leftarrow r+1.
\]

Both sides increment \`r\` exactly when \`P\` is true. This equivalence
holds for the supported pure-expression integer semantics; it is not an
assertion of machine-level overflow equivalence outside the unbounded
integer VM. The reverse rewrite is also available.

The mutation **search** is not proven optimal. Candidate acceptance
requires the static type checker, finite correctness tests against
independent Python task oracles, a validation corpus, and the explicit
VM fuel budget. Candidate selection uses a fixed separate **fitness**
corpus. Only after selection is the independent **withheld** corpus
evaluated. Correctness failure on withheld data aborts the result,
rather than silently claiming success.

## Performance model and baseline

An array program is assessed on three separable metrics:
value comparisons, array writes, and VM operation steps. These are
**modeled counts**, not measured latency or hardware efficiency.
For counting and membership, optimization is lexicographic:
comparisons → steps → writes → genome size.
For summation: steps → comparisons → writes → size.
For array clamping: writes → comparisons → steps → size.

The baseline is the real v3.0 \`algorithm_genome_v30.discover(task)\`
output, executed on the **same** v3.1 fitness and withheld input sets.
Never compare to another workload or quietly redefine the baseline.

### Local falsifiable result (seed 1907)

| Task | Structural effect | Fitness conclusion | Withheld conclusion |
| --- | --- | --- | --- |
| \`count\` | predicate increment → conditional branch | Lower VM steps, equal comparisons | Lower VM steps, equal comparisons |
| \`contains\` | loop reversal and related mutations | Fewer comparisons on selected workload | **No comparison improvement** on withheld |
| \`sum\` | explored mutations | No fitness improvement | No improvement |
| \`clamp\` | mutations across branches and array writes | No fitness improvement | No improvement |

On the separately withheld 51-case corpus for \`count\`, the local
prototype measured **150.45 → 120.80 interpreter steps per case**
(approximately 19.7% less), while comparisons stayed at 18.43.
This is a **microcost-model improvement**, not faster production code.
No latency superiority or new asymptotic algorithm claim follows.

The \`contains\` fitness-versus-withheld discrepancy is an important
**negative control** demonstrating workload overfitting. The project
must preserve it and must not claim a real-world membership speedup.

## Independent verification and falsification

- Type checker validates offspring after every structural edit.
- One known failed example short-circuits weak candidates.
- Exhaustive finite-domain training, independent validation,
  and an unseen 51-case benchmark protect the reported claim.
- Additional tests compare generated programs to Python built-in
  oracles on random signed 64-bit-ish integer arrays up to 128 items.
- Universal semantic equivalence of the particular predicate-increment
  rewrite follows directly from Boolean conversion; the entire
  evolved program has only finite observed correctness checks.
- Single-candidate and invalid-budget paths cannot announce success.
- Mutation rules, proposal count, training survivors, successive
  improvements, both genome ASTs and all benchmark metrics are
  serialized into the CI artifacts.

## Reproduction

    python -m unittest discover -s tests -v
    python genome_evolution_v31.py --task count --output v31_count.json
    python genome_evolution_v31.py --task contains --output v31_contains.json
    python genome_evolution_v31.py --task sum --output v31_sum.json
    python genome_evolution_v31.py --task clamp --output v31_clamp.json

No external package dependencies. Python 3.10 and 3.13 CI run the
complete suite, and the 3.13 job emits all four result JSONs.
The previous SyGuS/Z3 proof gate and sorting-stage invention gate remain
in place.

## Limitations / next step

- A small, explicitly bounded AST mutation neighborhood; no genetic
  crossover and no general multi-register state synthesis.
- The lexicographic objective can overfit one chosen workload.
  Multi-sample performance robustness and explicit Pareto frontiers
  are future work.
- Some mutations affect program semantics. Exhaustive testing on one
  finite corpus is not proof for arbitrary input arrays.
- Current interpreter exposes a small fixed statement grammar and
  no nested loops, heap allocation, aliasing or recursion.
- Next milestone: typed multi-register and two-loop data-structure
  genomes, genuine crossover, counterexample persistence, and
  blinded benchmarks with hardware timings.

## Release gate

Merge only after: both Python jobs green, \`count\` generated branch
has strictly fewer withheld interpreter steps than the unchanged v3.0
baseline with identical value comparisons, the \`contains\` negative
generalization is retained, \`sum\`/\`clamp\` unsuccessful searches
are reported, and v2.8/v2.9/v3.0 CI regressions pass.
