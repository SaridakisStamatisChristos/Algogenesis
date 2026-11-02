# AlgoGenesis v2.2 — Regret guarantee, online stability gate, and negative results

**SOTA is NOT established.** This release combines a classical bounded
expert-advice theorem with a separately measured empirical stability gate.
Neither is a new general-purpose algorithm synthesizer.

## Bounded guarantee (non-novel)

For outcomes y_t in a predeclared interval [a,b] and K fixed experts,
clip and quantize predictions to a grid of P ticks. Let
l_it=|p_it-y_t|/(b-a) in [0,1], q_it=ceil(Q*l_it)/Q, eta in (0,1/2].
Form the weighted average of expert predictions using positive weights
w_i initialized to 1, round the average to the P-tick grid, then update
weights after observing y_t by w_i <- w_i*(1-eta*q_it).

For EVERY bounded outcome sequence (adversarial or stochastic), the
normalized absolute-loss regret of the **rounded** learner relative
to the best fixed rounded expert is at most

  ceil(log2(K))/eta + eta*T + T/Q + T/(2*P).

This bound is checkable using exact Fraction arithmetic in
regret_forecast.BoundedExperts.certificate().

Proof: With W_t=sum_i w_it and pi_it=w_it/W_t, let qbar_t=sum_i
pi_it*q_it. Since W_(t+1)=W_t*(1-eta*qbar_t) and log(1-x)<=-x,
log W_(T+1)<=log K-eta*sum_t qbar_t. For any expert j,
W_(T+1)>=prod_t(1-eta*q_jt).
For 0<=x<=1/2, log(1-x)>=-x-x*x, so
log W_(T+1)>=-eta*sum_t q_jt-eta*eta*T.
Combining, sum_t qbar_t <= sum_t q_jt+log K/eta+eta*T.
By convexity of absolute error and rounding, learner loss at t is at
most qbar_t+1/(2P). Further, q_jt <= l_jt+1/Q. Minimize over j and
use log K<=ceil(log2(K)) to obtain the stated bound.

tuned_eta chooses eta=1/q for q approximately sqrt(T/ceil(log2K)).
With Q,P>=T, the bound has classical minimax-rate order
O(sqrt(T log K)+log K), but it does NOT have a novel best constant.
The bundled default uses Q=512,P=2**256. Increasing T beyond Q
requires increasing Q to retain this asymptotic rate.

The arithmetic initially became infeasible with unquantized rational
weight updates; separate loss and prediction grids repaired the issue.
The code rejects out-of-domain outcomes rather than expanding bounds
using future data. No production resource guarantee is asserted.

## Empirical selector

stability_selector.py accepts exact rational histories and uses an
additional rule: BM recurrence experts are eligible only after five
consecutive exact held-out one-step forecasts. Other experts (linear,
persistence, 3-point mean, seasonal naive, EWMA with two fixed smoothing
rates) remain available. Selection is by trailing mean error plus a
quarter of trailing maximum, and it uses no future samples. Finite
historical accuracy is not an oracle certificate.

## Five statsmodels historical series — local run, 2026-11-02

Mean absolute errors (MAE, lower better; units differ across rows):

Dataset | points scored | v2.1 | stability gate | bounded MW | best simple method
Nile annual flow | 68 | 129.029 | 113.170 | 143.075 | EWMA quarter: 103.168
Annual sunspots | 277 | 17.944 | 18.606 | 21.028 | linear: 16.504
Quarterly US real GDP | 171 | 56.220 | 56.230 | 185.153 | linear: 52.973
Quarterly US CPI | 171 | 0.654 | 0.603 | 2.816 | linear: 0.595
Quarterly US unemployment | 171 | 0.218 | 0.212 | 0.418 | linear: 0.196

Stability gate wins three streams against v2.1, loses on sunspots and
nearly ties on GDP. The bounded weights method is significantly WORSE
in these short streams despite its valid worst-case theoretical bound.
On the six synthetic families, the stability gate and v2.1 dominate
the bounded mixture on exact recurrences; no superiority claim is made.

## Reproduction and evidence

  python -m unittest discover -s tests -q
  python -m pip install statsmodels==0.14.6
  python regret_benchmark.py
  python regret_benchmark.py --synthetic

All methods are scored on identical one-step targets at indices >=32.
Input domains and seasonalities are declared ahead of scoring in
regret_benchmark.HISTORICAL_CONFIG. The known test length determines
the weight-learning rate but is not outcome leakage. MASE is normalized
by the initial 32-sample nonseasonal naive first-difference error, not
by errors fitted on the scoring horizon.

Independent GIFT-Eval/M4/Monash comparison, ARIMA/ETS reference methods,
held-out datasets, uncertainty intervals, and external replication
remain open. These historic series were available during development,
so they are NOT an independent blind test.

Theory source: https://www.math.univ-toulouse.fr/~sgerchin/docs/These-Gerchinovitz.pdf
Known limits: https://research.google/pubs/tight-lower-bounds-for-multiplicative-weights-algorithmic-families/
Benchmark reference: https://arxiv.org/abs/2410.10393
Historical datasets: https://www.statsmodels.org/stable/datasets/index.html

R7 evidence ledger:
- Causal one-step forecasts: TESTED locally (mutation tests)
- Bounded regret math: PROVED under specified model; implementation TESTED
- Finite-grid/resource fix: TESTED locally
- Historical scores: EXECUTED_LOCAL, not independently reproduced
- General algorithm synthesis SOTA: UNVERIFIED
- Global forecasting SOTA: UNVERIFIED
