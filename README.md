# AlgoGenesis v0.6 — Algorithm Discovery Research Laboratory

AlgoGenesis is a **bounded research prototype**, not a general algorithm-discovery system and not an established SOTA result. This repository includes the sorting-network search tracks, integer-expression CEGIS, a bounded register-machine interpreter, and two loop-synthesis tracks.

**Python:** 3.10+; no external dependencies.

## Run

From the repository root:

```bash
python -m unittest discover -s tests -v
python algogenesis.py --width 4 --generations 200 --population 64 --seed 42
python discovery.py --mode evolve --width 4 --generations 1000 --population 128 --seed 42
python discovery.py --mode exact --width 4
python advanced.py --mode benchmark --width 4 --trials 12 --generations 400 --population 80
python program_synthesis.py --task absdiff --bound 3
python program_synthesis.py --task maximum --bound 3
python loop_synthesis.py
python dynamic_synthesis.py
```

## Modules

| File | Purpose |
| --- | --- |
| `algogenesis.py` | v0.1 baseline-seeded evolutionary sorting-network search |
| `discovery.py` | v0.2 unseeded evolution, bit-parallel zero-one verification, exact semantic BFS for widths 2–4 |
| `advanced.py` | v0.3 semantic beam search, redundant-comparator pruning, independent scalar counterexamples, multi-seed benchmark |
| `program_synthesis.py` | v0.4 enumerative integer-expression synthesis with observational-equivalence pruning and counterexample-guided inductive synthesis |
| `control_flow.py` | v0.4 deterministic bounded register machine: integer expressions, comparisons, branches, bounded repeat, execution fuel |
| `loop_synthesis.py` | v0.5 finite candidate grammar for accumulator programs with input-specialized loop counts |
| `dynamic_synthesis.py` | v0.6 immutable AST with input-derived dynamic loop counts and finite-domain CEGIS |

## Correctness and limitations

A comparator network sorts every input over a totally ordered domain if it sorts all binary inputs of the same fixed width (zero-one principle). The bit-parallel verifier exhaustively checks those binary inputs. Exact BFS proves minimum comparator count only for widths 2–4; evolutionary and beam search do **not** establish optimality.

Expression synthesis searches ASTs over integer variables/constants and `neg`, `abs`, `add`, `sub`, `min`, `max`. It verifies only the selected finite domain and restarts the search when new counterexamples invalidate observational equivalence.

The interpreter has explicit fuel and bounded repeat counts; `loop_synthesis.py` specializes the AST to each input, whereas `dynamic_synthesis.py` builds one reusable AST with an input-dependent repeat bound. The dynamic synthesizer searches a small fixed family of accumulator programs and does not synthesize arbitrary loops, nested control flow, or loop invariants.

The v0.6 finite-domain experiments synthesize multiplication and negative multiplication on nonnegative integer pairs in `[0,6]^2` (49 cases). `x*x+y*y` is outside the searched grammar and is not found.

## Historical evidence

- v0.2: unseeded evolution found a five-comparator width-four sorting network, 56,794 unique evaluations for seed 42.
- v0.3: 12/12 width-four evolutionary trials found valid five-comparator networks; `benchmark_v03.json`.
- v0.4: 22 tests passed locally; `cegis_absdiff_v04.json` and `cegis_max_v04.json` record finite-domain syntheses.
- v0.5: 28 tests passed locally.
- v0.6: 38 tests passed locally on Python 3.13.5; `benchmark_v06.json` records finite-domain results.

The historical test transcripts `test_run_v04.txt`, `test_run_v05.txt`, and `test_run_v06.txt` are retained as evidence from prior local executions. These are **not** GitHub CI attestations. Rerun the suite on the current checkout to establish present correctness.

## Research next steps

Compositional loop and branch synthesis, invariant discovery, formal equivalence checks, diverse held-out tasks, and fair comparisons against established synthesis baselines are still required. No general-purpose algorithm invention, GPU acceleration, published SOTA result, or production readiness is claimed.

## v0.7 — Compositional synthesis and symbolic proof certificates

`compositional.py` synthesizes up to two sequential input-bounded accumulator loops with observational-equivalence pruning and CEGIS. Its interpreter is independent from its search-time arithmetic signature evaluator. It discovers programs for `x*y+x`, `x*y+y`, `x*x+y*y`, `2*x*y`, and `x*x-y*y` over a 25-case nonnegative input domain.

`certificates.py` normalizes the restricted loop grammar to six exact polynomial coefficients (constant, x, y, x², xy, y²). Under its documented assumptions (nonnegative counts, immutable inputs, unbounded integer accumulator, no branching), coefficient equality is a mathematical equivalence certificate for **all nonnegative integer x,y**, not merely the training domain. This does not prove general program-synthesis correctness or SOTA.

Run `python compositional.py`, `python certificates.py`, and `python -m unittest discover -s tests -v`. The local development tree passed 46 tests on Python 3.13.5. The GitHub Actions matrix is the independent repository verification gate.

## v0.8 — Nested-loop synthesis and cubic polynomial certificates

`nested_synthesis.py` synthesizes sequential accumulator updates containing one or two **nested** input-bounded loops. Its grammar represents degree-at-most-three integer polynomials through repeated addition/subtraction. The canonical ten-coefficient basis is `1,x,y,x²,xy,y²,x³,x²y,xy²,y³`.

The `certify` function checks exact coefficient equality for all nonnegative integer inputs under these assumptions: immutable loop bounds, no branching or side effects, and an unbounded integer accumulator. Synthesis uses CEGIS, with an independent interpreter checking the finite domain. New tests cover `x³`, `x²y`, `xy²`, `y³`, `x³+y³`, adversarial invalid inputs, and independent random-program evaluation.

Run `python nested_synthesis.py` and `python -m unittest discover -s tests -v`. The local v0.8 suite passed **51 tests**; GitHub CI is the separate repository gate. This is not general algorithm synthesis and does not establish SOTA.

## v0.9 — Conditional synthesis

`branch_synthesis.py` adds bounded-depth conditional program synthesis with affine leaves and comparisons over x, y, and zero. Search uses semantic partition memoization and counterexample-guided refinement; verification runs the generated AST through the independent `control_flow.Interpreter`. Tests cover max, min, absolute difference, conditional sign, and two-level clamp, with held-out inputs outside the training range. Finite-domain evidence and held-out testing do not prove unbounded correctness or establish SOTA.

Run `python branch_synthesis.py` and `python -m unittest discover -s tests -v`.

## v1.0 — Exact conditional-program equivalence (RFP + UCS-Pro R7)

`branch_certificates.py` proves equivalence of two supported `branch_synthesis.Node`
programs **for all integer pairs** `(x, y)` by partitioning the plane along
`x=0`, `y=0`, and `x=y`. The 13 relatively open cells comprise six 2D
sectors, six 1D rays, and the origin. Both programs are affine on each cell;
checking three non-collinear witnesses per sector, two distinct witnesses
per ray, and one at the origin is sufficient for equality throughout each
cell. An inequality returns a concrete integer counterexample.

The certificate assumes affine integer leaves, guards `lt/le/eq` comparing
only `x`, `y`, and `zero`, and pure unbounded-integer semantics. It does not
prove correctness against arbitrary Python oracle functions; it proves
**equivalence of two explicitly represented decision trees**. The independent
`control_flow.Interpreter` is also exercised on held-out inputs. The checker
is not a formally verified proof assistant.

Run `python -m unittest discover -s tests -v`. Local verification: 61 tests
passed on Python 3.13. GitHub CI provides separate revision-specific evidence.

## v1.1 — Exact counterexample-guided synthesis

`exact_cegis.py` connects the finite-example conditional synthesizer with the
exact piecewise-affine equivalence checker. Given a **reference AST** in the
supported grammar, the algorithm proposes a candidate from current examples,
asks the exact checker whether it agrees on *all integer input pairs*, and,
if not, adds the checker's concrete integer counterexample before searching
again. Only exactly certified candidates are returned as successful.

The `tests/test_exact_cegis.py` suite covers exact max/min/absdiff/clamp
synthesis, counterexample learning, insufficient grammar, resource exhaustion,
invalid inputs, and deterministic replay. Run `python exact_cegis.py` or
`python -m unittest discover -s tests -v`.

**Scope:** equivalence to an explicitly supplied reference program; no
automatic extraction of a reference AST from arbitrary Python, no proof of
general algorithm invention, and no established SOTA comparison.

## v1.2 — Mutable-state recurrence synthesis

`recurrence_synthesis.py` adds a loop-carried state register and synthesis of
programs of the form `acc=a; state=s; repeat(x): acc+=sign*state; state+=delta`.
The exact result is `a + sign*(s*x + delta*binomial(x,2))`. The certificate
normalizes to coefficients of `(1,x,binomial(x,2))` and proves equivalence
**between programs of this grammar** for all nonnegative integers, assuming
unbounded arithmetic and immutable `x`.

New tests compare the closed form with the independently executing register
interpreter for random programs and held-out values. Synthesis is finite-domain
oracle-guided; its returned polynomial certificate does not by itself prove
equivalence to an arbitrary Python oracle outside the sample domain. The
interpreter also enforces a per-loop bound of 10,000 and fuel limits, so its
execution contract is narrower than the mathematical closed form.

Run `python recurrence_synthesis.py` and
`python -m unittest discover -s tests -v`. No SOTA claim is made.
