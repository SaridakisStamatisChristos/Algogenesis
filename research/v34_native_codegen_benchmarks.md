# AlgoGenesis v3.4 — Native C Code Generation, Independent Verification and CPU Benchmarks

**Baseline:** merged v3.3 commit \`3d682eb5838a1870058ef90aaaa7a6747a74e896\`.
**Release objective:** measure actual compiled performance of *generated* typed algorithms against independent strong implementations, instead of relying on VM step/comparison counts.
**Research status:** executable native compiler and benchmarking laboratory; no global SOTA or novel-algorithm claim.

## Representation and semantics

\`native_codegen_v34.py\` translates the actual v3.3 \`Genome\` dataclasses (or their strict JSON encoding) into C11. It does **not** select a task-specific solution string or substitute a hand-written implementation. Supported expressions: signed 64-bit literals, typed register/input variables, \`read\`, \`add/sub\`, \`lt/eq\`, Boolean \`and/or/not\`, Boolean-to-integer conversion. Supported control flow: typed register assignment, \`if/else\`, forward/reverse \`foreach\` with a checked inclusive start index and optional early termination.

The current backend deliberately **rejects** mutable array \`store/swap\`, arbitrary output sorts, invalid C identifiers, unsupported operations, register reads outside their permitted scope, and literal integers outside the signed-int64 domain. Input array length is bounded to 4096 in emitted code; array reads abort if out of bounds.

Python's integer arithmetic is unbounded while native C signed integer overflow is undefined. Therefore this compiler claims semantic correspondence **only when intermediate arithmetic remains inside signed int64**. The benchmark restricts array elements to [-1000,1000] and length to <=4096, so count and extreme-sum intermediate results remain within int64. It makes **no** claim for overflow-containing inputs, pointer aliasing, concurrency, or arbitrary generated programs.

The deterministic C generator output and SHA-256 are preserved. GCC C11 compilation uses \`-O3 -fno-lto -Wall -Wextra -Werror\`. The compiler and host platform metadata are recorded.

## Independent correctness gates

1. Original v3.3 finite-domain Python validation and its independent task oracle.
2. Native candidate compared in the same C executable with a **separately written two-pass reference**, which itself agrees with the intended count/sum-of-extreme semantics across fixed and pseudorandom signed inputs.
3. The unit tests compile the generated C into a dynamic library and compare native outputs **directly against the independent Python task oracle**, on arrays of lengths 0, 1, 2, 3, 16, 64, 128, 512 and 4096.
4. A separately compiled \`-fsanitize=undefined -fno-sanitize-recover=all\` binary checks runtime validity. Failed compilation, incorrect outputs, sanitizer errors or missing raw measurements fail the release gate.
5. Tests reject unsupported mutable-array programs, malformed serialized ASTs, code-injection identifier attempts, out-of-range literals, and incorrect benchmarking budgets.

These gates support **empirical cross-language correctness on the tested domain**, not a machine-checked universal equivalence theorem.

## Native benchmark design

\`native_benchmark_v34.py\` generates one C source containing:
- \`ag_generated\`: the actual typed AST compiled from the preserved v3.3 artifact.
- \`ag_ref_better\`: a correct, separately implemented better-first one-pass reference.
- \`ag_ref_equal\`: a correct, separately implemented equality-first one-pass reference.
- \`ag_ref_two_pass\`: an independent two-pass correctness oracle.

Each benchmark candidate has the same C signature and is called through volatile function pointers to prevent inlining/dead-code elimination. All functions are compiled in the same translation unit with equivalent compiler flags, and benchmark order rotates across repetitions. The benchmark uses a monotonic clock, checksum consumption, warmup and five repeated measurements.

18 public workload cells per task: lengths **16/128/1024**, six distributions (**uniform, duplicate-heavy, all-equal, increasing, decreasing, alternating**), fixed deterministic seeds. Each record includes every raw per-repetition timing and separate medians for generated, better-first and equality-first code. The stronger comparison is the *smaller of the two reference medians in each cell*, which is deliberately conservative about the generated candidate's relative competitiveness. This is not a pre-registered overall single-policy competitor: report all cells, not only wins.

These are **repeated same-array, likely warm-cache microbenchmarks**; branch predictor, compiler optimization, CPU frequency, thermal contention, VM host placement and measurement order can dominate outcomes. Raw evidence can reveal such noise. No general throughput/latency speedup or hardware-independent ranking is asserted.

## Local preliminary run, GCC 14.2 \`-O3\`

Each task uses 5 repetitions in 18 cells. Median generated/reference latency ratio across cells, reference = faster of two strong one-pass C implementations:

| Task | Median ratio | Cells generated faster | Cells generated slower |
| --- | ---: | ---: | ---: |
| count_max | 1.41x | 4 | 14 |
| count_min | 1.29x | 3 | 15 |
| sum_max | 1.41x | 1 | 17 |
| sum_min | 1.52x | 2 | 16 |

All four programs passed native correctness and UBSan locally. A ratio > 1 indicates the generated program is **slower**, not faster.

**Falsification:** the v3.3 improvement in *modeled comparisons* does **not** imply improved compiled C speed. The resulting v3.4 finding is negative for global SOTA, but establishes measurable, reproduced engineering ground truth. The GitHub-hosted CI machine is not assumed to reproduce the same numerical ratios; it must preserve its own raw measurements.

## Reproduction

\`\`\`bash
python -m unittest discover -s tests -v
for task in count_max count_min sum_max sum_min; do
  python genome_headtail_v33.py --task "$task" --output "v33_$task.json"
  python native_benchmark_v34.py --task "$task" \
      --genome-json "v33_$task.json" \
      --repetitions 5 --elements-per-sample 500000 \
      --output-dir native_v34_evidence
done
\`\`\`

GitHub CI must retain v2.8 Z3/SyGuS, v2.9 sorting-network, v3.0 typed-genome, v3.1 structural-evolution, v3.2 crossover/fusion and v3.3 head-tail synthesis gates. CI uploads the 12 native files: four generated C sources, four raw CSV timing logs and four detailed JSON reports.

## The next scientifically justified experiment

**Native-guided program search (v3.5):** use a separate *selection* workload to rank generated AST variants by native executable performance, not by VM cost. Hold back an independent native evaluation distribution and CPU/configuration, include strong branchless or vectorized reference implementations when relevant, and track per-distribution regressions and uncertainty. Avoid selecting on the same measurement cells used to claim speedups.

**SOTA prerequisites:** a precisely stated problem/metric/comparison class, up-to-date strong published/reference algorithms, comparable compiler and hardware settings, independent held-out workload families, statistical confidence, and separate correctness proof. v3.4 does not meet that bar and must be reported as such.
