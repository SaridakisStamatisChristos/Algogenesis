# v3.9: independently summarized lanes

This phase adds a different algorithmic state structure to AlgoGenesis.
Indices with even and odd parity maintain separate extrema and frequencies;
a final expression merges the two partial summaries. The implementation
adds typed integer bitwise AND to express the partition predicate. It does
not insert a prewritten task-specific winning program. A task-neutral grammar
enumerates 1,536 complete ASTs by varying comparison direction, equality
order, initialization, reset, increment, scan direction, and merge direction.
The independent task oracle rejects invalid programs before ranking.

For a correct candidate, the intended invariant is: after any scan step,
`best0/frequency0` summarizes the visited even-indexed elements, while
`best1/frequency1` summarizes the odd-indexed elements. The merge chooses
the lane with the stronger extremum, or adds the two frequencies on a tie.
The tests inspect both partial registers over exhaustive small arrays;
the 51-case disjoint Python holdout and a native C/UBSan oracle provide
additional finite evidence. These checks do not constitute a universal proof
for every generated candidate.

The local finite search found 8 valid `count_max`, 8 `count_min`, 32
`sum_max`, and 32 `sum_min` genomes. The selected genome for each task is
chosen by VM operations on the fitness set. Native timing happens afterward
on a fixed twelve-cell evaluation set and a separate seed. Source, AST,
raw timings, all losses, compiler metadata, and negative results are
published by CI. Performance wins are never required for release.

```sh
python -m unittest tests.test_genome_striped_v39 -v
python genome_striped_v39.py --task count_max --output-dir native_v39_evidence
```

This is a new algorithmic family for this generator, distinct from its
one-state scan and select-expression variants. Striped reduction itself is
a known technique; no worldwide novelty is claimed. Current scalar C
generation branches on parity and may be slower than simpler references.
Future work should expose vector lanes and block summaries as typed,
composable operators and search their merge laws under invariants.
