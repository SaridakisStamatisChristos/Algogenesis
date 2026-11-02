# AlgoGenesis v2.1 — Historical-series falsification

The v2.1 synthetic results do not establish SOTA. We independently
assess two real historical datasets from statsmodels 0.14.6 using the
optional real_world_validation.py runner. The AlgoGenesis core requires
only the Python standard library; this optional assessment requires
pip install statsmodels==0.14.6.

One-step prequential evaluation: positions 0-31 calibrate; points 32+
are scored with absolute error divided by (1+absolute actual).
All models receive the same inputs and score periods. Reference methods:
adaptive ensemble selector, guarded short/long BM, linear, persistence,
and seasonal naive at lag 11. Rationals are exact internally and final
displayed mean errors are floats.

Locally measured with Python 3.13.5 and statsmodels 0.14.6:

Dataset | evaluated | adaptive | linear | persistence | seasonal naive 11
Nile river flow 1871-1970 | 68 | 0.153125 | 0.262031 | 0.153125 | 0.197489
Annual sunspots 1700-2008 | 277 | 0.533090 | 0.509110 | 0.529010 | 0.824900

IMPORTANT NEGATIVE RESULT: adaptive ties persistence on the Nile and
loses to linear on sunspots. The general superiority claim is falsified.
This is not a modern SOTA evaluation; Monash / GIFT-Eval / M4, stronger
ARIMA/ETS baselines, multiple horizons, CIs, and independent replication
remain open.

Source: statsmodels public-domain historical datasets.
https://www.statsmodels.org/stable/datasets/index.html

R7 status: functionality tested; external-series numbers measured locally,
but independent reproduction not established. SOTA UNVERIFIED.
