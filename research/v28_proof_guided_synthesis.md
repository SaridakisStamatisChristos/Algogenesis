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
