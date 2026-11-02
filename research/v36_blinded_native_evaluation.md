# v3.6: selection-isolated native evaluation

This experiment addresses the specific leakage in v3.5: the reusable runner
used to time every candidate on all 18 cells, including the twelve cells
nominally withheld from the ranking score. v3.6 requests **only six cells**
in each candidate profiling process. After the winner index is fixed, a
separate process measures the winner and v3.3 baseline on twelve evaluation
cells. The partitions and 64-bit data seeds are constants in
`native_blinded_v36.py` and recorded in the JSON evidence.

The v3.4 runner now accepts a cell mask and data seed. It still runs its
correctness and UBSan checks; these are not performance measurements. The
native timing loop skips all excluded cells before generating their inputs.
The evaluation seed differs from the selection seed. Both programs are tested
on the same deterministic evaluation arrays for a paired workload comparison,
although their executable timings run separately.

Run the experiment for each task:

```sh
python -m unittest tests.test_native_blinded_v36 -v
python native_blinded_v36.py --task count_max --output-dir native_v36_evidence
```

The CI workflow executes all four tasks and publishes source, raw CSV,
candidate profiles, selected and baseline measurements, and losses. A valid
release requires correct partition provenance, native verification and UBSan;
it does not require winning a performance comparison.

## Interpretation

This is a **frozen protocol, fresh-seed evaluation**, not a concealed or
independent laboratory holdout. The partitions and seeds are public; do not
change them after inspecting results and continue calling the same data
unseen. The arrays still repeat within a timing cell and remain warm in cache.
Compilation, process order, runner contention, and the single CPU can affect
timing. Discovery uses finite Python examples; native execution checks a
bounded signed-int64 no-overflow domain. No universal equivalence proof or
broader SOTA claim follows.

The next comparator gate should add semantics-matched branchless and
vectorized implementations, then interleave timings across machines and
toolchains with uncertainty estimates. Richer search and formal proof remain
separate research gates.
