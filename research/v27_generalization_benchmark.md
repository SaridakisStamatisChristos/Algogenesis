# AlgoGenesis v2.7 — Structural generalization and frozen external benchmark campaign

Baseline: `9a6ff710d28dad0d5b1efb0ea20e89f6efc39a7c` (v2.6). Date: 2026-11-02.

## Objective and scope

Increase the restricted integer synthesizer's provable coverage beyond four
arguments without claiming open-ended general algorithm invention. Evaluate it
against cvc5 with the same bounded task-level wall-clock budget, preserved
upstream task text, and independent Z3 checks of emitted programs.

## New mechanism

`structural_max.py` accepts exactly the contract over 2–6 declared integer
variables consisting of (i) one source constraint `f(x)>=x_i` for each
argument and (ii) an OR asserting that `f(x)` equals one of the inputs.
Duplicates, altered bounds, missing alternatives and unrelated constraints
are rejected. The recognizer uses actual parsed source constraints, not names
such as "max5" or a benchmark filename.

**Correctness argument.** In a totally ordered domain, if `f(x)>=x_i` for
every i and `f(x)=x_j` for some j, then `f(x)=max_i x_i`. A tournament
over the input variables constructs the winner. Because the existing AST
grammar permits guards comparing *variables* but not arbitrary computed
expressions, a winner-vs-challenger comparison is distributed into every
incumbent leaf. For n inputs, the emitted decision tree has exactly
`2^n-1` nodes, while execution examines n-1 comparisons per path.
This is deliberately bounded at n<=6, **not** a scaling solution.
Its accepted outputs still require external UNSAT from Z3 before benchmark
"proved" classification. The internal weak-order certificate stays bounded
to four arguments.

## Frozen and provenance-checked external cases

`benchmarks/sygus_manifest_v27.json` lists eleven SyGuS-Org tasks pinned at
`13c8deb68a873635879c9a69bc78caebd340f646`, retaining their source Git
blob SHAs. The benchmark harness rehashes every loaded byte. It includes the
original max2/max3/max4/diff, previously unsupported max5/max6, deliberately
out-of-scope max7/max8, weakly specified small, and VC22_a/VC22_b with helper
functions and multiple synthesis targets. This is **curated challenge
sampling**, not a random/representative competition cohort.

Official source:
https://github.com/SyGuS-Org/benchmarks/tree/13c8deb68a873635879c9a69bc78caebd340f646

## Execution and interpretation

Run from the repository root with Z3 on PATH and ideally cvc5 on PATH:

    python -m unittest discover -s tests -v
    python structural_max.py benchmarks/sygus_clia_v27/max5.sl
    python structural_max.py benchmarks/sygus_clia_v27/max6.sl
    python benchmark_v27.py --timeout 5 --z3-timeout 15 --repeats 3 --output benchmark_v27_results.json

GitHub CI executes a one-repetition smoke comparison, publishes the raw
JSON artifact, and **requires Z3 UNSAT** for generated max5 and max6
candidates. Both engines run as independent subprocesses and share the same
per-task wall-clock timeout. Start-up costs are included. Independent Z3
checks occur after synthesis and do not affect synthesis elapsed times.

A cvc5 solution outside the existing restricted AST parser is classified
`unverified`, not failed, and **does not mean cvc5 is incorrect**. Similarly
`unsupported` is a coverage limitation, not a proof of unsatisfiability.
Any missing cvc5 binary, timeout, malformed response, or missing Z3
verification remains explicitly represented. Solver output semantic validity
is established only for solutions that the shared verifier can read.

## Threat model and falsification

- A benchmark text mutation changes its Git blob SHA and aborts the run.
- A changed >, equality or omitted alternative cannot trigger the max rule.
- External Z3 must refute a violating original constraint for both max5/max6.
- An intentionally wrong max5 candidate must yield SAT.
- The benchmark driver must not equate `unknown`, missing solver or
  unsupported syntax with a verified solution.
- Complexity is exponential in emitted tree size, so max7/max8 are intended
  negative scale controls and no extension to unbounded arity is claimed.

## Limitations and subsequent path

This is a family-specific structural reduction, not an unrestricted
synthesizer. The restricted solver still cannot handle helper function
definitions, multiple synthesis functions, arbitrary guards, nonlinear
updates, or arbitrary SyGuS-IF. This benchmark set is small and correlated,
and a single CI repetition is an integration gate, not a statistically
persuasive performance ranking. For a defensible comparative SOTA claim:
adopt a prospectively chosen broader competition subset, use an
unrestricted independent checker for solver outputs, pin executable
versions and hardware, repeat trials, report complete denominators and
unfavorable outcomes, and optimize a genuinely general synthesis mechanism.

**Evidence gate:** tests present are not tests passed until actual CI execution
logs at the exact candidate SHA have been inspected. Results belong in the
published JSON artifact, not in unverified claims in this document.


## v2.7 extension — DAG representation and baseline verification coverage

The initial audited 11-task run established 6/11 AlgoGenesis solutions and
9/11 cvc5 solutions as independently Z3-verified at a five-second wall
timeout. Some cvc5 solutions used let-bound affine guards and helper
functions; a verification-only parser now reserializes their original
source constraints and candidate definitions into a guarded SMT-LIB query.
No source-provided assertions, options or arbitrary commands are emitted.
Malformed, unsupported and ambiguous texts remain unverified.

To test the representational scaling limit without the 2^n decision-tree
expansion, synthesize_linear_max emits shared SMT-LIB 'let' temporaries
for n<=16. After processing k inputs the champion register equals their
maximum, by induction: the next guard selects max(champion, x_(k+1)).
This yields n-1 comparisons and O(n) textual and DAG size, with n-1
runtime comparison steps. The proof argument applies to a totally ordered
domain and the exact recognized source contract. Z3 is the independent
external proof gate, not a substitute for the structural argument.

The challenge corpus was extended from 11 to 12 cases by including the
pinned official 2018 CLIA max16 task; the selected family remains
overrepresented and cannot establish general-purpose synthesis SOTA.
The old internal certifier is still limited to <=4 inputs, and the
general CEGIS synthesizer to <=4 inputs: admitting up to 16 *parsed*
arguments is not the same as a 16-variable general synthesis capability.

Interpret results on the 12-task suite separately from the historical
11-task results. The v2.7 extension increases the number of solvable
max-family tasks, while off-family tasks such as weakly specified small
and the complex VC22 templates remain substantive capability gaps.
