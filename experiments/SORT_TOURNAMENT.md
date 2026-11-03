# R7 × Sol sorting tournament — experimental checkpoint

Three structurally distinct mechanisms are implemented in `experiments/sort_tournament.py`:

1. **run_merge**: detect natural ascending runs, then pairwise stable merge. Worst-case O(n log n) time and O(n) auxiliary space; already-sorted O(n). Not a novelty claim: related to natural mergesort/Timsort.
2. **sparse_distribution**: integer range test, bounded counting array, and merge fallback. O(n + R) time and O(n + R) space when R <= 8n; fallback O(n log n). Counting-sort hybrid is established prior art.
3. **three_way_blocks**: iterative median-of-three three-way partitioning, insertion-sort leaves, and depth-bounded merge fallback. O(n log n) worst-case time; O(n) fallback space. Introspective three-way quicksort is established prior art.

Inputs are integer sequences. All return new sorted lists; no key/comparator interface is promised. Counting candidate can be generalized only after separate key/stability verification. Baseline is Python's `sorted` (Timsort); C++ std::sort requires a separately matched C++ implementation and must not be directly compared with Python timings.

## Reproduce
```sh
python -m unittest discover -s tests -p 'test_sort_tournament.py'
python -m experiments.benchmark_sort_tournament --sizes 100 1000 10000 --repeats 11 --seed 1729 > tournament.json
```

## Adversarial controls
Exhaustive ternary arrays through length 7, reversed/sorted/all-equal, alternating signs, huge sparse integer ranges, duplicate-heavy arrays, partition cutoffs, deterministic seeded random arrays, and no mutation of inputs.

## Evidence gate
Correctness requires actual test execution; performance requires measured output with machine provenance. No novelty or SOTA assertion. A proper tournament additionally needs warmup, paired randomized ordering, confidence intervals, memory profiling, multiple machines, and language-matched C++ std::sort comparisons. Existing repository synthesis and test infrastructure is unchanged.
