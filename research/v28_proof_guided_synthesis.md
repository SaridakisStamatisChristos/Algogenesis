# AlgoGenesis v2.8 — Proof-guided finite SyGuS synthesis (research gate)

Base: v2.7 \`6412ce649764792fe23d96cccb137a86288e5ec9\`
Date: 2026-11-02

## Motivation

The v2.7 general enumerator assigns one preferred output label to each
finite input. In specifications with *many* valid outputs, this may
exclude otherwise correct programs before any universal proof is
attempted. The official SyGuS CLIA \`small.sl\` is one example.
The restrictive \`parse_problem\` also rejects helper-function
definitions and multiple synthesis targets even though the external
SMT verification path already supports both.

## New algorithm (bounded, deterministic)

\`proof_guided_synthesis.py\` enumerates a small grammar of arithmetic
leaves and guarded conditionals over the input arguments. It does not
read task names or memorize official solutions. For two synthesis
targets sharing the same integer argument signature, it enumerates
shared expressions first and then a bounded Cartesian product of
independently selected functions.

For each complete candidate, the independent \`sygus_general_checker\`
re-parses the candidate and the original SyGuS constraints, forms
the negation of the universal specification and calls Z3.
Only the external SMT answer **UNSAT** produces \`proved\`.
\`SAT\` rejects that candidate; \`UNKNOWN\`, missing Z3, parse error,
subprocess error, or timeout cannot produce success.
The verifier handles helper definitions and source function calls
in the restricted SyGuS text syntax, but remains a trusted
implementation, not a proof-assistant kernel.

Formally, for a source specification \`forall v: C(v,F)\`, a candidate
\`F*\` is accepted only if Z3 reports UNSAT on
\`exists v: not C(v,F*)\`. Under the accepted formula semantics and
a sound solver, this is sufficient for universal validity. The
bounded enumeration is not a decision procedure: failing to find
a candidate does not prove no program exists.

The finite grammar is not intended to be state of the art; its value
is to separate *search objective* from an arbitrary pointwise label
and permit all original constraints (including multiple functions)
to determine global candidate correctness.

## Scope and bounds

- One or two grammar-free Int synthesis functions with 1–2 Int
  arguments each, and common argument names for joint synthesis.
- Leaves include constants and variables; expressions include
  linear addition/subtraction and one conditional with comparisons.
- Candidate limit 160; worker solver budget 3.25 seconds,
  subquery timeout 0.35 seconds; fail-closed outcomes.
- Full 12-task frozen, source-hashed suite from v2.7 reused,
  including max2-max8, max16, diff, small, VC22_a, VC22_b.
- The original exact maximum-family recognizer and bounded
  pointwise-label synthesizer remain the fast paths.
- Proof-guided enumeration runs only after those fail or reject
  the source grammar. The comparative benchmark includes all
  its solver work in AlgoGenesis elapsed wall-clock time.

## Reproduction

With Z3 and optionally cvc5 on PATH:

    python -m unittest discover -s tests -v
    python benchmark_v27.py --timeout 5 --z3-timeout 15 --repeats 1 --output benchmark_v28_results.json --require-proved small.sl,VC22_a.sl

The CI Python 3.13 gate also retains the five maximum-family
certificates and complete existing tests. CI publishes raw JSON.

## Risks and falsifiers

1. **Candidate search bias** — the grammar is finite. Failure to
   solve a task is only a failure of this grammar/budget.
2. **Unsound source encoding** — malicious or unsupported commands
   must be rejected by the independent checker, not silently dropped.
3. **Correlated proof assumptions** — all independently verified
   candidates share the same trusted SMT-LIB translator and Z3
   backend, so this is not two independent formal verifiers.
4. **Benchmarks** — the selected 12-case corpus overrepresents
   maximum tasks. Any 12-task success rate is an exploratory result
   and cannot support a SyGuS-Comp or general-SOTA claim.
5. **Comparison fairness** — cvc5 and AlgoGenesis use the same
   per-task process timeout, but potentially different implementation
   internals and the same external Z3 validity checker. Negative
   statuses, timing and machine/software versions must be kept.
6. **Joint search** — the two-function enumerator is intentionally
   incomplete; identical functions are searched first, not assumed
   to be the only possible solutions.

## Decisions

The immediate acceptance gate is Z3-verified solutions for the
previously unsolved, underconstrained \`small.sl\` and helper-function
\`VC22_a.sl\`, with no regression to v2.7 exact certificates. The
multi-target \`VC22_b.sl\` outcome must be reported whether success
or failure; it is not a hidden release blocker.

Next substantial advancement after v2.8 should be *solver-driven
counterexample extraction*, sample replay and grammar-growth
prioritization rather than increasing special-family templates.


## Initial observed results (evidence: PR #3, run 41445327787)

**Revision** \`eb21c20212e75cc541a76a53835d7f9f708063e8\`;
Python 3.13.17 on GitHub's Linux x86_64 hosted runner;
Z3 4.13.3, cvc5 1.3.2. Frozen, provenance-checked
12-case manifest; one comparison repetition, five-second subprocess
timeout per engine. The CI matrix passed (195 tests on 3.13 and the
Python 3.10 suite). Raw CI artifact:
https://github.com/SaridakisStamatisChristos/Algogenesis/actions/runs/41445327787

| Benchmark | AlgoGenesis status | AlgoGenesis synthesis ms | cvc5 status | cvc5 synthesis ms |
| --- | --- | ---: | --- | ---: |
| max2 | proved | 51.80 | proved | 7.84 |
| max3 | proved | 53.40 | proved | 8.52 |
| max4 | proved | 51.36 | proved | 9.91 |
| diff | proved | 55.42 | timeout | 5008.08 |
| max5 | proved | 52.18 | proved | 12.19 |
| max6 | proved | 53.98 | proved | 15.46 |
| max7 | proved | 53.81 | proved | 21.84 |
| max8 | proved | 56.14 | proved | 32.30 |
| small | proved | 653.65 | proved | 87.81 |
| VC22_a | proved | 229.89 | proved | 498.33 |
| VC22_b | proved | 229.48 | timeout | 5008.10 |
| max16 | proved | 50.31 | proved | 2700.93 |

The new generic fallback produced these candidates (not benchmark-name
special cases): \`small: (ite (< x y) y x)\`,
\`VC22_a: (ite (= x1 x2) 0 1)\`,
and **both** \`VC22_b\` synthesized functions equal
\`(ite (= x1 x2) 0 1)\`. The independent SMT verifier returned
UNSAT for the negation of the original constraints for each.

**Interpretation:** 12/12 for AlgoGenesis, 10/12 for cvc5 within this
specific five-second exploratory protocol. This is not a general
solver capability or speed ranking. cvc5 is faster on most of the
easy max cases and on small. The benchmark set is highly curated,
contains known easy structural families, and the initial report has
a single repetition. The later three-repetition CI gate is a
reproducibility check, not a substitute for a broader blinded
competition-quality benchmark.

## Residual engineering obligations

- Add genuine solver counterexample extraction / caching and evolve
  syntax trees to make this more than bounded brute-force enumeration.
- Expand source grammar and synth grammar while preserving external
  check of the *original source*, not a lossy rewrite.
- Perform independently sampled benchmarks against multiple available
  current solvers; include time distribution, unsupported fractions
  and resource caps.
- Do not equate correct solutions on these 12 tasks with
  a novel algorithmic discovery or general SOTA.
