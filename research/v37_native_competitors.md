# v3.7: stronger native comparators

This phase fixes the selected genome from each v3.6 result and measures it in
one C translation unit against four independently implemented references:
better-first scalar, equality-first scalar, conditional-update scalar, and an
AVX2 two-pass extrema/count reduction when the CPU supports AVX2. The latter
uses runtime feature detection and a function target attribute, so a machine
without AVX2 reports its absence and measures only the scalar competitors.

Each function is checked against the separate two-pass task oracle over all
six array families, varied sizes, and randomized finite examples. A second
binary reruns these checks under UndefinedBehaviorSanitizer. The timed loop
rotates function order within each repetition and publishes all raw samples,
per-cell medians, the winning reference in each cell, generated C, compiler
flags, and hardware metadata. Ratios use the fastest valid reference in each
cell. The input domain is bounded signed int64 arrays whose task sums do not
overflow. The AVX2 two-pass result is `count * extreme` for sum tasks; this
identity is valid in the tested domain.

```sh
python native_blinded_v36.py --task count_max --output-dir native_v36_evidence
python native_comparators_v37.py --task count_max \
  --v36-result native_v36_evidence/v36_count_max.json \
  --output-dir native_v37_evidence
```

CI runs all four tasks and publishes the evidence. This comparison reuses the
already disclosed v3.6 evaluation cell *families*, though it has a new fixed
random seed. It is an expanded comparator check on a frozen winner, not a new
blinded independent benchmark. The harness still repeats a warm array and
runs on one hosted runner. AVX-512/NEON, established library baselines,
multiple machines and compilers, confidence intervals, broader task families,
and formal program equivalence remain open. A release requires complete,
correct evidence; it never requires a performance win or makes a SOTA claim.
