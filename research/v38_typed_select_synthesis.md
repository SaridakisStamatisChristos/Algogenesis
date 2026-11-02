# v3.8: a new generated algorithm family

The v3.3 generator varied branch order inside a one-pass extrema scan. v3.8
extends the typed language with `select(condition, yes, no)`. Type checking
requires a Boolean condition and equal branch sorts. The VM evaluates only
the chosen branch, as does the generated C conditional expression.

The new task-neutral grammar enumerates 1,536 complete ASTs. Each has a
first-element guard and a scan that updates both `best` and `frequency`
through conditional expressions **without an `if` statement inside the
loop**. It varies comparison direction, equality form, initialization,
reset and increment expressions, update order, scan direction, and two
aggregation forms. No task-specific winning AST is injected. Independent
task oracles reject incorrect programs before native profiling.

The finite screen found 8 correct genomes each for `count_max` and
`count_min`, and 16 each for `sum_max` and `sum_min` locally. These are
structurally distinct from the 768 v3.3 candidates. Native selection
profiles a deterministic sample of new correct genomes alongside the actual
v3.3 generated baseline on six cells only. It freezes the winning index and
the best *new* index before evaluating either on the twelve-cell holdout,
with a separate seed. The baseline is evaluated on the same holdout. Both
the overall winner and best new structure are reported even if the baseline
wins. The frozen candidates also pass a separate 51-case Python holdout
before native evaluation. CI publishes ASTs, source, raw samples, rankings
and losses.

```sh
python -m unittest tests.test_genome_select_v38 -v
python genome_select_v38.py --task count_max --output-dir native_v38_evidence
```

**Meaning of new:** the software generated an algorithm structure not in
its previous grammar. This does not establish a previously unknown algorithm
in the literature or a performance advance. The native benchmark remains a
single-machine warm-array experiment; the new family may be slower than
strong scalar or AVX2 references. Correctness is finite-domain evidence,
not a universal proof. Further search should add semantically distinct
representations such as invariant-constrained block reductions and vector
operations, then compare fairly across machines and compilers.
