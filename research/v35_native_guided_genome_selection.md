# AlgoGenesis v3.5 — Native-Guided Algorithm Genome Selection

**Base:** merged v3.4 \`b444dd4204d975cb8a3b57b402a912b5f10e32b5\`.
**Goal:** make actual native CPU latency (not operation-count proxies) an explicit objective for selecting among *generated, correct, typed algorithm genomes*.

## Pipeline

1. Enumerate **768 program structures** from the v3.3 task-independent, typed head/tail grammar.
2. Independently filter on task oracles: a small counterexample screen, exhaustive 781-case finite training domain and disjoint validation arrays. No speed evidence can excuse a correctness failure.
3. Preserve the genuine v3.3-generated genome as a baseline. Select up to six other correctly typed and empirically verified candidate structures from the grammar by a fixed, deterministic, evenly spaced sampling rule. The baseline is always included; no human-supplied optimized implementation is inserted.
4. Compile each selected candidate to real native C11 via the v3.4 AST compiler. Check its results against independent C and Python task oracles, compile under GCC -O3, and rerun under UndefinedBehaviorSanitizer.
5. Measure native latency with rotating function order and C reference comparators. Select using **geometric mean of candidate/faster-reference median latency ratios** across six predefined training cells, with genome size/index only for deterministic ties.
6. **After selection**, recompile and benchmark the chosen genome and the original v3.3 genome with more repetitions/operations, and report native results on 12 designated evaluation cells. Publish all candidates and rejected outcomes, every held-out loss, the raw native timings, generated C code, and compiler/platform metadata.

### Fixed benchmark partitions

- Selection cells: \`length in {16,128}\`, \`distribution in {uniform,duplicates,all_equal}\` = 6 cells.
- Evaluation cells: \`length in {16,128,1024}\`, \`distribution in {increasing,decreasing,alternating}\`, plus \`length=1024\` on the remaining three distributions = 12 cells.

**Scope qualification:** the reusable v3.4 benchmark harness *also measures* the 12 evaluation cells during candidate profiling, although the v3.5 ranking code only accesses the six training-cell values. Therefore these are **held out from selection logic, not fully unseen or independently generated data**. The final selected-vs-baseline experiment is rerun with separate timing samples, but the inputs and CPU remain related. This distinction prevents claims of strict blinded hardware-validation or cross-machine generalization. Moving to fresh independently seeded final data and cross-compiler CPU replicas remains required.

### Statistical and correctness restrictions

- Real native CPU latency; task semantics and fixed signed-int64 input domain, not Python VM steps.
- Comparison reference is the faster of **two** separately written, correctness-checked native one-pass solutions (better-first and equality-first), on each cell.
- Every generated candidate must pass native C oracle, Python corpus, and UBSan. A failure is preserved as a rejection, not hidden.
- Per-cell raw repetitions and medians are published. Speed estimates on a shared CI machine are noisy; this is not a statistically definitive performance ranking.
- A score below 1 indicates the generated candidate is faster on the **chosen local microbenchmark**; it is not global SOTA.
- No claim is made about globally novel algorithms, universally correct unbounded programs, hardware-independent throughput, optimized SIMD baselines, or published algorithmic SOTA.

## Prior motivating observation

A separate local count-maximum probe tested four semantically correct branches/scans. The best tuning variant approached reference parity and won 6/12 designated evaluation cells, but still lost overall there. This observation motivated v3.5; the hosted CI experiment must record its **own** results and may select a different candidate.

## Reproduce

\`\`\`bash
python -m unittest discover -s tests -v
python native_autotune_v35.py --task count_max --max-profiles 6 \
  --training-repetitions 3 --training-elements 150000 \
  --final-repetitions 5 --final-elements 500000 \
  --output-dir native_v35_evidence
\`\`\`

Repeat for \`count_min\`, \`sum_max\`, \`sum_min\`. The GitHub-hosted CI gate runs all four, preserving the earlier native v3.4, sorting, typed-genome, and SyGuS/Z3 regression checks. The release **does not require a favorable benchmark result**: correctness, reproducibility, transparent candidate ranking and faithful reporting are the acceptance criteria.

## Next SOTA-directed research gates

1. True final-input blinding with fresh deterministic seeds and separate benchmark runners.
2. Strong optimized and vectorized native reference families (not only scalar branch orders).
3. Multiple CPU architectures and toolchains, warm- and cold-cache regimes, confidence intervals and workload stratification.
4. Search over a richer typed genome (invariants, vector operations, memory layouts, multi-loop recurrences) to escape the present 768-program finite family.
5. Independent solver-backed proof where possible. Do not conflate finite testing with a universal proof.

**Verdict vocabulary:** \`native_experiment_complete\` denotes a completed experiment regardless of performance. Any favorable result can be reported only for the exact workload and toolchain on which it was measured.
