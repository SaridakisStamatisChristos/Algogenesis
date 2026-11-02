"""Causal adaptive expert selection for exact-rational scalar sequences.

Four fixed candidates: short/long Berlekamp-Massey, linear extrapolation,
persistence. Exact forecasts and errors; scores use only previously observed
outcomes. This is not an optimality or forecasting-SOTA guarantee.
"""
from dataclasses import dataclass
from fractions import Fraction
from berlekamp_massey import infer

EXPERTS = ("bm_short", "bm_long", "linear", "persistence")


@dataclass(frozen=True)
class Forecast:
    index: int
    selected: str
    predicted: Fraction
    observed: Fraction
    candidates: tuple[tuple[str, Fraction], ...]
    scores: tuple[tuple[str, Fraction | None], ...]

    @property
    def absolute_error(self):
        return abs(self.predicted - self.observed)


@dataclass(frozen=True)
class Evaluation:
    records: tuple[Forecast, ...]
    selected_mae: Fraction
    candidate_mae: tuple[tuple[str, Fraction], ...]
    selected_relative_mae: Fraction
    candidate_relative_mae: tuple[tuple[str, Fraction], ...]
    switches: int


def _predict(history, name, short, long):
    if name == "persistence":
        return Fraction(history[-1])
    if name == "linear":
        return Fraction(2 * history[-1] - history[-2])
    width = short if name == "bm_short" else long
    segment = history[-width:]
    forecast = Fraction(infer(segment).predict_next(segment))
    # Prevent explosive extrapolations; fall back to the last observation
    # when the predicted exact rational exceeds the configured bit budget.
    if forecast.numerator.bit_length() > 512 or forecast.denominator.bit_length() > 512:
        return Fraction(history[-1])
    return forecast


def evaluate(observations, *, warmup=32, short=8, long=20, lookback=12, calibration=12):
    """Evaluate one-step prequential forecasts with disjoint scoring phases.

    Expert selection minimizes mean plus maximum recent relative error.
    Calibration observations precede the forecast window and affect only
    selection, NOT the reported held-out metrics. Each per-step prediction
    and selection uses observations at indices strictly before that step.
    """
    values = tuple(observations)
    if any(type(v) not in (int, Fraction) for v in values):
        raise TypeError("observations must be exact ints or Fractions (no bools)")
    if any(type(v) is not int for v in (warmup, short, long, lookback, calibration)):
        raise TypeError("evaluation parameters must be integers")
    if short < 3 or short > long or long < 3 or lookback < 1 or calibration < 1 or warmup - calibration < long:
        raise ValueError("require 3 <= short <= long <= warmup-calibration, lookback and calibration >= 1")
    if len(values) <= warmup:
        raise ValueError("at least one held-out online observation required")
    losses = {name: [] for name in EXPERTS}
    absolute = {name: [] for name in EXPERTS}
    evaluation_losses = {name: [] for name in EXPERTS}
    records = []
    for index in range(warmup-calibration, warmup):
        history = values[:index]
        actual = Fraction(values[index])
        for name in EXPERTS:
            prediction = _predict(history, name, short, long)
            losses[name].append(abs(prediction-actual)/(1+abs(actual)))
    for index in range(warmup, len(values)):
        history = values[:index]
        candidates = {name: _predict(history, name, short, long) for name in EXPERTS}
        scores = {name: ((sum(losses[name][-lookback:], Fraction(0)) /
                         len(losses[name][-lookback:]) + max(losses[name][-lookback:]))
                         if losses[name] else None)
                  for name in EXPERTS}
        selected = min(EXPERTS, key=lambda name: (
            scores[name] is None,
            scores[name] if scores[name] is not None else Fraction(0),
            EXPERTS.index(name)
        ))
        actual = Fraction(values[index])
        records.append(Forecast(index, selected, candidates[selected], actual,
                                tuple(candidates.items()), tuple(scores.items())))
        denominator = 1+abs(actual)
        for name, prediction in candidates.items():
            error = abs(prediction-actual)
            absolute[name].append(error)
            losses[name].append(error/denominator)
            evaluation_losses[name].append(error/denominator)
    count = len(records)
    return Evaluation(
        records=tuple(records),
        selected_mae=sum((r.absolute_error for r in records), Fraction(0))/count,
        candidate_mae=tuple((name, sum(absolute[name], Fraction(0))/count) for name in EXPERTS),
        selected_relative_mae=sum((r.absolute_error/(1+abs(r.observed)) for r in records), Fraction(0))/count,
        candidate_relative_mae=tuple((name, sum(evaluation_losses[name], Fraction(0))/count) for name in EXPERTS),
        switches=sum(a.selected != b.selected for a,b in zip(records, records[1:]))
    )
