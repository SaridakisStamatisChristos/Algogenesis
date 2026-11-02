# AlgoGenesis v2.3 — Switching-expert tracking and falsification

**Research status: classical algorithm implemented and tested; global SOTA NOT established.**

## Definition and prior art

This module implements the Fixed-Share algorithm for switching between
forecasting experts, first studied by Mark Herbster and Manfred K. Warmuth
in "Tracking the Best Expert" (Machine Learning 1998).
The contribution here is a Python exact-rational implementation, a
quantization-aware certificate, a switch-budget exact comparator oracle,
and reproducible adversarial/statistical benchmarks, NOT a new theorem.

References:
- https://mlanthology.org/mlj/1998/herbster1998mlj-tracking/
- https://proceedings.mlr.press/v76/mourtada17a/mourtada17a.pdf
- https://github.com/SalesforceAIResearch/gift-eval
- https://www.statsmodels.org/stable/datasets/index.html

## Regret contract

Let K be the expert count. Every observation must belong to an outcome
interval [a,b] specified BEFORE scoring, and every expert prediction is
clipped and rounded to a P-tick grid on that interval. Define loss

    ell(i,t) = |prediction(i,t) - outcome(t)| / (b-a)   in [0,1].

Use Q-grid upward-quantized losses q(i,t)=ceil(Q*ell(i,t))/Q.
Start with weights w(i,1)=1. Predict with the rounded weighted mean,
then AFTER seeing the true outcome update weights by

    v(i,t) = w(i,t) * (1-eta*q(i,t))
    w(i,t+1) = (1-alpha)*v(i,t) + (alpha/K)*sum_j v(j,t).

Assume 0<eta<=1/2, 0<alpha<1, Q>=2 and P>=2.
For EVERY expert path i(1)..i(T) containing S switches, the normalized
cumulative absolute loss regret satisfies:

    R(T) <= [ceil(log2 K)
             +(T-1-S)*alpha/(1-alpha)
             +S*ceil(log2(K/alpha))] / eta
            +eta*T +T/Q +T/(2P).

This statement applies to bounded expert-advice regret, NOT general
program synthesis or time-series forecasting optimality.

## Proof

Define total weight W(t)=sum_i w(i,t), pi(i,t)=w(i,t)/W(t), and
qbar(t)=sum_i pi(i,t)*q(i,t). Share redistribution preserves weight,
hence W(t+1)/W(t)=1-eta*qbar(t).

The update can also be viewed as a mixture over expert paths with
initial uniform prior 1/K and transition probability
(1-alpha)*I(current=previous)+alpha/K. Every path with S actual
switches therefore receives prior mass at least

    p(path) >= (1/K)*(1-alpha)^(T-1-S)*(alpha/K)^S.

Since each prior path incurs product_t(1-eta*q(i(t),t)), the weight
potential satisfies

    log(W(T+1)/W(1))
      >= log(p(path)) + sum_t log(1-eta*q(i(t),t)).

On the other hand,

    log(W(T+1)/W(1)) = sum_t log(1-eta*qbar(t))
                     <= -eta*sum_t qbar(t).

The inequalities log(1-x)>=-x-x^2 for x in [0,1/2],
q<=1, and log(1-x)<=-x imply

    sum_t qbar(t) - sum_t q(i(t),t)
        <= -log(p(path))/eta + eta*T.

By convexity of absolute loss, the rounded learner's normalized loss
per time step is at most qbar(t)+1/(2P). Each expert's upward quantized
loss is at most its unquantized loss plus 1/Q.
Finally, use

    log(K) <= ceil(log2 K)
    -log(1-alpha) <= alpha/(1-alpha)
    log(K/alpha) <= ceil(log2(K/alpha)).

Substitution proves the stated pathwise bound.

The certificate is calculated in exact Python fractions. It is a
finite numerical witness within these documented mathematical
assumptions, NOT a standalone formal verification by Lean/Coq.

## Comparator oracle and tuning

The offline best-path comparison uses exact dynamic programming over
time, expert identity and switch count. It needs O(T*K^2*S) operations
and O(T*K*S) predecessor memory. The oracle never chooses predictions
during live forecasting; it is used only after all outcomes are known.
For T rounds, K experts, and a *predeclared* switch budget S, tuning
alpha and eta uses only these public metadata, not evaluation outcomes.

## Adversarial tests

The suite exhausts all 64 binary outcomes of length six against all 64
two-expert comparison paths, validates dynamic programming against
brute-force enumeration, tests 12 randomized streams, and includes a
1,000-round experiment with a non-vacuous (<T) regret bound.

Constructed sequence: 100 zeros, 100 ones, 100 zeros; experts predict
constant zero and constant one. With eta=1/4 and alpha=1/16:

| Method | Cumulative absolute loss |
| --- | ---: |
| Original fixed-weight mixture | 103.1654 |
| Fixed-Share mixture | 46.7423 |
| Best comparator with two switches | 0 |

With declared horizon T=300, K=2, S=2, tuning instead chooses
eta=1/4 and alpha=2/301. Fixed-Share learner loss is 33.5327 and
its exact bound against the zero-loss comparator is 159.5324.
This is a positive constructed result, not a claim of general
empirical accuracy.

## Statistical head-to-head, negative result

All methods use the first 32 historical observations for initialization.
Each later point is predicted before being observed. ARIMA(1,1,0) is
fit ONCE with statsmodels SARIMAX on the prefix; its states are extended
causally after each observed point, with no parameter refit. SES and
Holt parameters are likewise fitted on the same prefix, followed by
standard causal filter updates. All columns are mean absolute error
(MAE, lower is better), each in its own native units.

| Dataset | Static mixture | Fixed-Share tuned | Persistence | ARIMA(1,1,0) | SES | Holt |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Nile flow (68 forecasts) | 125.984 | 135.025 | 129.029 | 120.079 | 109.408 | **108.532** |
| Annual sunspots (277) | 18.653 | 20.240 | 18.706 | **15.195** | 18.706 | 18.898 |
| US real GDP (171) | 175.941 | 180.250 | 69.176 | 49.783 | 69.176 | **44.209** |
| US CPI (171) | 2.737 | 2.789 | 1.174 | 0.686 | 1.174 | **0.562** |
| US unemployment (171) | 0.387 | 0.407 | 0.236 | **0.187** | 0.236 | 0.239 |

**Falsification:** Fixed-Share does not beat the strongest statistical
comparator on ANY of these five real historical datasets. These are
development-visible data, not an independent blind evaluation.
ARIMA initial parameter fits raised convergence warnings on CPI and
unemployment; the machine-readable report retains these flags.
All methods are tested for one-step predictions only, not comparable to
modern multi-horizon GIFT-Eval leaderboards.

## Reproduction

    python -m unittest discover -s tests -q
    python -m pip install statsmodels==0.14.6
    python tracking_benchmark.py

The optional statsmodels tests may be skipped by CI. Runtime recorded
for the combined benchmark does not constitute matched per-method
microbenchmarking. The stored numerical results are from Python 3.13.5
and statsmodels 0.14.6, not a separately reproduced environment.

## Evidence ledger

- Exact pathwise regret statement: human-checkable PROOF, scope restricted.
- Implementation, comparator oracle, random/adversarial tests: TESTED_LOCAL.
- CI status: inspect the actual workflow associated with latest commit.
- Five historical datasets: EXECUTED_LOCAL, unfavorable to Fixed-Share.
- Independent 2026 forecasting leaderboard SOTA: NOT ESTABLISHED.
- General-purpose algorithm discovery SOTA: NOT ESTABLISHED.
