# AlgoGenesis v2.4 — Official SyGuS CLIA tasks and universal certificates

**Four selected official third-party SyGuS integer-synthesis benchmarks have been solved in a restricted solver fragment. This is not a SyGuS-Comp SOTA claim.**

## Source fidelity

Source: https://github.com/SyGuS-Org/benchmarks
Pinned upstream Git commit: 13c8deb68a873635879c9a69bc78caebd340f646
Directory: lib/CLIA_Track/from_2018

| Vendored file | Official filename | Source Git blob SHA |
| --- | --- | --- |
| max2.sl | jmbl_fg_max2.sl | da6f241315239f82c1d85eac3f40c7ebbbd0c03b |
| max3.sl | jmbl_fg_max3.sl | b516e782ac02f1c2fc63bc3735f20e7a38fdbb93 |
| max4.sl | jmbl_fg_max4.sl | d7682dd5ad55c7dad26b5b98df8b16c1df7f49aa |
| diff.sl | diff.sl | c9e770e1e88a904ce514319bf02f84c5ecb28a83 |

The copies were obtained directly from the upstream GitHub files and preserve their original text. This is a **deliberately selected four-task subset**, not a random representative sample or competition run.

## Exact supported contract

One grammar-free integer synthesis function with 1–4 distinct integer inputs, set-logic LIA, declare-var, constraint and check-synth. Supported input constraint operators: integer linear + and -, comparisons =, <, <=, >, >=, Boolean and/or/not/implies. A recognized binary function symmetry condition permits the relational swap used by diff. The synthesized candidate grammar consists of decision trees with input/zero comparison guards and bounded affine leaves.

Explicit grammars, arbitrary ite within the benchmark specification, helper functions, multiple synthesis functions, bit-vectors, quantifiers and many other official SyGuS constructs are NOT supported. Unknown syntax is rejected. The parser is NOT claimed as SyGuS-IF 2.1 compliant overall.

Finite synthesis first derives candidate pointwise output targets over the grid [-2,2]^n. Bounded CEGIS searches decision trees and tests the *original constraints* on the full grid. Under the explicit symmetry condition, a deterministic preference resolves ambiguous local targets; this is a heuristic and may miss other valid solutions. A candidate only counts as proved after the universal verifier succeeds.

## Why the universal certificate is sound in this fragment

For n input variables, consider all possible weak orders (including ties) among x1,...,xn and constant zero. Every integer assignment belongs to exactly one such order type. For n=1,2,3,4 there are respectively 3, 13, 75 and 541 types.

Within a weak-order cell, values in consecutive distinct equality groups are separated by integer gaps g_j >= 1; the group containing zero fixes translation. Every input x_i is a signed sum of these gaps.

Every candidate guard compares input variables (or zero), so its truth is fixed on a weak-order cell; the synthesized tree therefore reduces there to an integer affine function. The difference D of any two expressions compared by an original constraint has the form

    D = c + sum_j w_j*g_j
      = (c + sum_j w_j) + sum_j w_j*h_j, h_j = g_j-1 >= 0.

If all coefficients w_j >= 0, D attains its minimum at all gaps equal to 1; otherwise its infimum is unbounded below. If all w_j <= 0, D attains its maximum at all gaps equal to 1; otherwise its supremum is unbounded above. These are exact arithmetic bounds, not samples. They certify when a comparison is always true, always false, or not determined by the cell. Three-valued Boolean evaluation is conservative: a task receives the PROVED status only if *every original constraint is provably true in every cell*. Unknown cell results cause abstention; false cell results return a concrete feasible integer witness.

Because the weak-order cells partition all integer assignments, passing all cells proves the constraints for every integer input, **under this restricted grammar and trusted implementation**. This is a human-auditable mathematical argument, not a formal Lean/Coq proof and not an independently invoked SMT checker.

## Observed results

Local Python 3.13.5, default training grid [-2,2]^n:

| Official task | Sample count used in CEGIS | Partitions explored | Grid points | Exact order cells | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| max2 | 3 | 5 | 25 | 13 | PROVED |
| max3 | 9 | 52 | 125 | 75 | PROVED |
| max4 | 25 | 866 | 625 | 541 | PROVED |
| diff | 3 | 5 | 25 | 13 | PROVED |

The max tasks synthesize maxima, and diff synthesizes an absolute-difference implementation satisfying the source's symmetry relation. Runtime is machine-specific; no cross-solver speedup is claimed.

## Reproduction and adversarial checks

Run from repository root on Python 3.10+ with no external dependencies:

    python -m unittest discover -s tests -q
    python sygus_benchmark.py
    python sygus_clia.py benchmarks/sygus_clia/max4.sl --depth 3
    python sygus_clia.py benchmarks/sygus_clia/diff.sl --depth 1

Tests exercise external benchmark end-to-end synthesis, independent direct evaluation on large-magnitude integer inputs, all order-region counts, invalid ASTs, a deliberately false candidate with a real counterexample, finite-grid overfit abstention, malformed source rejection and randomized certificate falsification.

**Evidence verdict:** 4/4 on the selected subset only. There is no independent external SMT solver run, no official SyGuS syntax checker run, no matched competition baselines, and no demonstrated algorithm-discovery SOTA. Next steps: a larger prespecified SyGuS benchmark set, independent SMT proof/checker, stronger grammar support, then fair comparison against current recognized solvers such as CVC5.
