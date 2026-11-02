# AlgoGenesis v2.1 — Prequential expert selection

Research target: **one-step online exact-rational scalar forecasting**, not general algorithm synthesis or state-of-the-art time-series prediction.

Run:
- python -m unittest discover -s tests -q
- python adaptive_benchmark.py

## Contract
- Four deterministic experts: Berlekamp–Massey with short (8) or long (20) window, first-order linear extrapolation, persistence.
- All predictions for time t depend only on data at times < t.
- Calibration uses the prefix ending at t=31, separately from scored observations t=32..63; no test observation affects its own prediction or selection.
- Selector minimizes mean+maximum *historical* relative loss over lookback=12, with deterministic tie breaking.
- The relative error is |prediction-actual|/(1+|actual|). Mean metrics are computed on exactly the same held-out 32 steps for every expert; calibration losses are excluded.
- Rational predictions and per-sequence arithmetic are exact; cross-sequence summary uses floating-point summation, and measured times are hardware dependent.
- Berlekamp–Massey extrapolations with numerator/denominator over 512 bits use a persistence fallback. This is an operational guard, not a mathematical proof that the prediction has low error.
- Objective is to reduce spikes due to noise; abrupt regime changes before observation remain unpredictable.

## Deterministic evidence
Seeded benchmark has six families (quadratic, exponential, periodic, impulse contamination, a regime switch, and random walk) with six instances per family, length 64. Baselines and adaptive model share identical inputs, evaluation periods, and loss functions.

Local Python 3.13.5 mean relative error (lower better):

| Seed | Adaptive | Linear | Persistence |
| --- | ---: | ---: | ---: |
| 20261102 | 0.032819 | 0.41832 | 0.42001 |
| 20261103 | 0.052057 | 0.447787 | 0.440723 |
| 12345 | 0.061519 | 0.442568 | 0.447183 |
| 777 | 0.067364 | 0.449680 | 0.449202 |

These are **synthetic results on related fixed generation families**, not independent real-world datasets, and the approach was iteratively refined against the same families. Do not interpret as SOTA, an independent test, a statistical significance result, or a guarantee under arbitrary noise.

The earlier baseline-metric computation mistakenly included calibration errors; this version excludes calibration and regression-tests exact per-record metric recomputation.

## External verification obligations
Evaluate on reproducible real-world time-series with predefined splits, e.g. Monash Forecasting Archive, M4 and GIFT-Eval; include stronger baselines such as ETS, ARIMA, seasonal naive and relevant streaming models. Report MASE, runtime, memory, confidence intervals, forecast horizons and both wins and losses. Separate forecasting SOTA from general algorithm synthesis. Independent reproduction and benchmarking are still open.
