# AlgoGenesis v2.6 — External SMT verification of restricted SyGuS candidates

Date: 2026-11-02
Candidate branch: research/v26-independent-smt-validation
Baseline: 324254d5d614998a59fa4aeb4e9bd4e2f7f1276f

## Research question

Does an independently implemented integer SMT solver find a violating
assignment for each synthesized candidate, under the *original* benchmark
constraints, rather than merely agreeing with AlgoGenesis' own order-cell
certificate?

## Independent obligation

Let C_1(v,F), ..., C_k(v,F) be the original parsed SyGuS constraints
over all integers v and synthesized function F. Our independent SMT check
constructs the quantifier-free formula

    exists v in Z^n: NOT (C_1(v,F) AND ... AND C_k(v,F)).

SMT-LIB translation uses a nonrecursive define-fun for F, globally declared
Int inputs, and one assert containing the negated conjunction.

If a sound SMT solver answers UNSAT, the formula has no model, so the
candidate satisfies all source constraints for every integer tuple.
SAT is evidence of a violating assignment; UNKNOWN is inconclusive.

The source and candidate use the restricted fragment accepted by the repository
parser: one integer synth-fun, 1–4 integer arguments, affine expression trees,
guards comparing argument variables or zero, and source constraints built from
integer +/-, comparisons and specified Boolean connectives. Unsupported or
ill-typed constructs are rejected before an external subprocess can execute.

## Assumptions and evidence separation

* The Python source parser, solution parser and SMT-LIB encoding are trusted
  software; they are not mechanized formal proofs.
* Z3 and cvc5 implement SMT-LIB QF_LIA soundly within their execution model.
* The subprocess actually executes the intended solver binary. The bridge
  reports the selected solver name, but does not pin binaries or attest their
  supply-chain provenance.
* The independent solver does not share the in-house order-cell sign-analysis
  algorithm. This gives independent *solver reasoning*, not independent
  ingestion of unrestricted original SyGuS-IF specifications.
* An UNSAT result is only a validity certificate for the presented candidate;
  it does not certify algorithm novelty, optimality or success on unseen tasks.
* The prior 4/4 score was for four deliberately selected official benchmarks,
  not a representative or blind sampling of competition tasks.

## Fail-closed tests

- Reject unsupported arithmetic, malformed candidate text, disallowed
  signatures and extra commands before subprocess dispatch.
- Query retains swapped synth-fun arguments in the external 'diff' constraint.
- Negative integers use canonical SMT-LIB unary minus; affine coefficients can
  use linear multiplication by numeral, valid in QF_LIA.
- An external UNSAT response yields 'proved' only when return code is zero
  and exactly one response line is present.
- SAT, UNKNOWN, timeout, missing solver, nonzero exit and malformed output
  never yield 'proved'.
- With real Z3 installed, each of max2/max3/max4/diff must return UNSAT.
- A deliberately incorrect candidate for max2 must return SAT.

## Reproduction

From repository root with Z3 installed:

    python -m unittest discover -s tests -v
    python sygus_smt_bridge.py --all --solver z3 --timeout 30

Optional: cvc5 installed on PATH

    python sygus_smt_bridge.py --all --solver cvc5 --timeout 30

GitHub Actions executes the external Z3 gate on Python 3.13. Z3 is not
required for the package's core runtime. CI logs must be inspected at the
candidate SHA before calling these external proofs *observed*.

## Remaining obstacles to comparative SOTA

1. Prespecify a substantially larger, stratified, non-cherry-picked
   SyGuS benchmark set and report full unsupported/timeout outcomes.
2. Extend syntax/semantics to benchmark grammars beyond the small affine
   decision-tree fragment while preserving sound rejection and proof gates.
3. Run fair pinned-version baseline comparisons with cvc5 and other recognized
   SyGuS tools under matched hardware, resource limits and repetitions.
4. Report solved counts, validity, search resources and time distributions
   including negative results; use reproducible scripts and artifacts.
5. Validate parser/encoder interoperability and independent solver output,
   ideally via at least two external implementations.

Verdict for v2.6: independent validity *infrastructure*, not confirmed
comparative state of the art. External solver execution evidence is supplied
by CI only after its run completes successfully.
