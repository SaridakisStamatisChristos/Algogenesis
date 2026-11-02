"""Exact fixed-grid multiplicative-weights forecasting with regret certificate.

This is a classical expert-advice algorithm, not a novel SOTA theorem.
A fine prediction grid and coarser loss grid keep exact-rational state tractable.
The additive discretization term is INCLUDED in the worst-case bound.
"""
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt


def _exact(value):
    if type(value) not in (int, Fraction):
        raise TypeError('only exact rational observations and predictions allowed')
    return Fraction(value)


@dataclass(frozen=True)
class Round:
    index: int
    actual: Fraction
    prediction: Fraction
    candidates: tuple[tuple[str, Fraction], ...]
    weights_before: tuple[tuple[str, Fraction], ...]
    learner_loss: Fraction
    expert_losses: tuple[tuple[str, Fraction], ...]
    update_losses: tuple[tuple[str, Fraction], ...]


@dataclass(frozen=True)
class Certificate:
    rounds: int
    learner_loss: Fraction
    best_expert_loss: Fraction
    regret: Fraction
    bound: Fraction
    valid: bool


class BoundedExperts:
    """Causal forecast/observe two-phase state machine, exact arithmetic."""

    def __init__(self, experts, *, lower, upper, eta=Fraction(1, 8),
                 resolution=512, prediction_resolution=(1 << 256)):
        names = tuple(experts)
        if not names or any(type(n) is not str or not n for n in names) or len(set(names)) != len(names):
            raise ValueError('expert names must be nonempty and distinct')
        self.lower = _exact(lower)
        self.upper = _exact(upper)
        self.eta = _exact(eta)
        if self.lower >= self.upper:
            raise ValueError('upper must exceed lower')
        if not 0 < self.eta <= Fraction(1, 2):
            raise ValueError('eta must be in (0, 1/2]')
        if type(resolution) is not int or not 2 <= resolution <= (1 << 20):
            raise ValueError('resolution must be integer in [2, 2**20]')
        if (type(prediction_resolution) is not int
                or not 2 <= prediction_resolution <= (1 << 1024)):
            raise ValueError('invalid prediction resolution')
        self.resolution = resolution
        self.prediction_resolution = prediction_resolution
        self.names = names
        self.weights = {name: Fraction(1) for name in names}
        self.records = []
        self._pending = None

    def _clip(self, value):
        v = min(self.upper, max(self.lower, _exact(value)))
        # Nonnegative fixed-grid offset, round half up.
        fraction = (v-self.lower)*self.prediction_resolution/(self.upper-self.lower)
        ticks = (2*fraction.numerator + fraction.denominator)//(2*fraction.denominator)
        return self.lower + (self.upper-self.lower)*Fraction(ticks,self.prediction_resolution)

    def _round_up_loss(self, loss):
        # The update loss exceeds the true loss by less than 1/resolution.
        scaled = loss*self.resolution
        ticks = (scaled.numerator + scaled.denominator-1)//scaled.denominator
        return Fraction(ticks,self.resolution)

    def predict(self, candidates):
        if self._pending is not None:
            raise RuntimeError('must observe before predicting again')
        if not isinstance(candidates, dict) or set(candidates) != set(self.names):
            raise ValueError('provide exactly one prediction per expert')
        forecasts = tuple((name, self._clip(candidates[name])) for name in self.names)
        weights = tuple((name, self.weights[name]) for name in self.names)
        weight_sum = sum(self.weights.values(), Fraction(0))
        mean = sum((self.weights[name] * value for name, value in forecasts), Fraction(0)) / weight_sum
        prediction = self._clip(mean)
        self._pending = (prediction, forecasts, weights)
        return prediction

    def observe(self, actual):
        if self._pending is None:
            raise RuntimeError('predict before observe')
        y = _exact(actual)
        if y < self.lower or y > self.upper:
            # Do not mutate weights or pending state upon invalid input.
            raise ValueError('observation outside predeclared outcome interval')
        prediction, forecasts, weights = self._pending
        distance = self.upper - self.lower
        losses = tuple((name, abs(value - y) / distance) for name, value in forecasts)
        learner_loss = abs(prediction-y) / distance
        rounded = tuple((name, self._round_up_loss(loss)) for name,loss in losses)
        rec = Round(len(self.records), y, prediction, forecasts, weights, learner_loss, losses, rounded)
        for name, loss in rounded:
            self.weights[name] *= 1 - self.eta * loss
        self.records.append(rec)
        self._pending = None
        return rec

    def certificate(self):
        if self._pending is not None:
            raise RuntimeError('finish pending forecast before certifying')
        t = len(self.records)
        learner_loss = sum((r.learner_loss for r in self.records), Fraction(0))
        expert_totals = [sum((dict(r.expert_losses)[n] for r in self.records), Fraction(0)) for n in self.names]
        best = min(expert_totals)
        # ceil(log2(K)) >= ln(K), an integer-only conservative bound.
        upper_bound = (Fraction((len(self.names) - 1).bit_length(), 1)/self.eta
                       + self.eta * t + Fraction(t, self.resolution)
                       + Fraction(t, 2*self.prediction_resolution))
        regret = learner_loss - best
        return Certificate(t, learner_loss, best, regret, upper_bound, regret <= upper_bound)


EXPERTS = ('persistence', 'linear', 'mean3', 'seasonal',
           'ewma_quarter', 'ewma_three_quarters', 'bm_short', 'bm_long')


def tuned_eta(horizon, experts=EXPERTS):
    """Choose 1/q <= 1/2 with q >= sqrt(T / ceil(log2 K)).

    The resulting bound is O(sqrt(T log K) + log K), provided the
    horizon is declared before forecasting. This is a known rate.
    """
    if type(horizon) is not int or horizon < 1:
        raise ValueError('horizon must be a positive integer')
    k = len(tuple(experts))
    if not k:
        raise ValueError('at least one expert required')
    log_bound = max(1, (k - 1).bit_length())
    q = max(2, isqrt(horizon // log_bound))
    while q * q * log_bound < horizon:
        q += 1
    return Fraction(1, q)


def _ewma(history, alpha, window=16):
    seq = history[-window:]
    estimate = Fraction(seq[0])
    for item in seq[1:]:
        estimate = alpha * item + (1-alpha) * estimate
    return estimate


def causal_candidates(history, *, season=11, short=8, long=20):
    if len(history) < max(season, long, 3):
        raise ValueError('insufficient history for experts')
    from adaptive_forecast import _predict
    return {
        'persistence': Fraction(history[-1]),
        'linear': Fraction(2 * history[-1] - history[-2]),
        'mean3': sum((Fraction(v) for v in history[-3:]), Fraction(0)) / 3,
        'seasonal': Fraction(history[-season]),
        'ewma_quarter': _ewma(history, Fraction(1,4)),
        'ewma_three_quarters': _ewma(history, Fraction(3,4)),
        'bm_short': _predict(history, 'bm_short', short, long),
        'bm_long': _predict(history, 'bm_long', short, long),
    }


def evaluate(observations, *, lower, upper, warmup=32, eta=Fraction(1, 8), season=11, resolution=512,
             prediction_resolution=(1 << 256)):
    series = tuple(_exact(v) for v in observations)
    if type(warmup) is not int or warmup < 20 or warmup >= len(series):
        raise ValueError('warmup must be >=20 and leave a held-out suffix')
    if type(season) is not int or not 1 <= season <= warmup:
        raise ValueError('season must be in [1, warmup]')
    aggregator = BoundedExperts(EXPERTS, lower=lower, upper=upper, eta=eta, resolution=resolution,
                                prediction_resolution=prediction_resolution)
    for index in range(warmup, len(series)):
        aggregator.predict(causal_candidates(series[:index], season=season))
        aggregator.observe(series[index])
    return aggregator
