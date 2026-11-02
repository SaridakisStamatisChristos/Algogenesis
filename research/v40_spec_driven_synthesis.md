# v4.0: specification-driven streaming algorithm synthesis

## Objective and interface

The caller supplies a JSON task, not a task identifier from a built-in
catalog. Each labeled case has `values: [int64, ...]`, `key: int64`, and
`expected: int64`. Four disjoint partitions are required: training,
validation, challenge, and holdout. Inputs are arrays of at most 128
elements. Duplicate `(values, key)` inputs are rejected across partitions.
The example in `examples/positive_even_sum_v40.json` requests the sum of
positive elements at even positions without presenting that algorithm in
the generator.

Run:

```bash
python spec_synthesis_v40.py --spec examples/positive_even_sum_v40.json --output-dir v40_generated
python -m unittest tests.test_spec_synthesis_v40 -v
```

The output directory contains `v40_<name>.json` (selected typed AST,
counts, counterexamples, generated source digest, native checks, and
limitations) and `v40_<name>.c` (standalone C11 function). The C function
accepts an array, its length, and the key and returns a signed 64-bit
result. By default, the CLI requires a working GCC compiler. Use
`--native-compiler none` only when intentionally skipping native execution;
the report then says `native_verification: null`.

## Search and falsification

The task-independent grammar enumerates 4,840 typed loop programs: a
single integer register initialized to zero, one, minus one, or the
first array item; forward or reverse traversal; and additions,
assignments, or conditional updates. Predicates compare the item with
the key, zero, or accumulator, test index parity, and combine selected
predicates with Boolean and/or. The VM type-checks candidates and
executes them against training and validation examples. Survivors are
ranked by AST size, comparisons, interpreter steps, and stable AST order.

For each ranked proposal, challenge cases are checked. A failing case is
kept as a counterexample and immediately removes other inconsistent
survivors. The Python API can also enumerate a bounded input domain with
an external `oracle(values, key)` and use those outputs as additional
counterexamples. Oracle inputs overlapping the holdout are excluded.
Once a candidate survives, the winner is frozen and checked against the
holdout exactly once. A failure raises an error instead of selecting a
different candidate. GCC compiles and executes the generated C at `-O3`
and again with undefined-behavior sanitization on the labeled cases.

## Observations and negative controls

The positive-even-sum example produces a zero-initialized forward fold
with a conjunction of `item > 0` and even index, conditionally adding
the item. It explored 4,840 proposals, retained four after training and
validation, and passed 65 challenge plus 30 held-out cases. Both native
executables passed 127 cases in total. Renaming the JSON task yields the
same AST, ruling out task-name dispatch in this demonstration.

Tests also synthesize different ASTs for key-occurrence counting,
maximum with zero on empty input, and alternating signed sum. A sparse
positive-even-sum specification causes the bounded oracle to produce
counterexamples before a surviving algorithm is selected. Malformed
specifications and an incorrect holdout fail closed.

## Evidence boundary

This is concrete algorithm generation within a restricted streaming-fold
DSL. There is no search over arbitrary data structures, nested loops,
recursion, arbitrary constants, or asymptotic complexity classes. A
finite sample and a bounded oracle cannot prove general correctness;
integer overflow and out-of-domain inputs require separate reasoning.
The native gate checks the produced C on the finite cases, including
UBSan, but does not prove semantic equivalence for all inputs. Search
ranking optimizes structural and VM operation measures, not native
speed. There is no claim of a new result in the literature or SOTA
performance.
