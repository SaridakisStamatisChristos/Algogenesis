"""Online change-point monitoring for exact scalar recurrence predictions.

One-step prequential protocol: predict from past data, observe, score,
then update. After a mismatch, refit on a short suffix. No prediction
can use the value being predicted. An arbitrary unannounced change
cannot be predicted in advance; the first surprise remains an error.
"""
from dataclasses import dataclass
from fractions import Fraction
from observable_recurrence import synthesize
from berlekamp_massey import infer

@dataclass(frozen=True)
class Event:
    index:int
    actual:Fraction
    prediction:Fraction|None
    method:str
    mismatch:bool|None
    alarm:bool
    train_start:int

@dataclass(frozen=True)
class OnlineResult:
    events:tuple[Event,...]
    alarms:tuple[int,...]
    covered:int
    exact:int
    errors:tuple[Fraction,...]

def _fit_predict(window,method):
    if method=="hankel":
        result=synthesize(window)
        if result.model is None:return None
        return result.model.generate(len(window)+1)[-1]
    if method=="bm":
        result=infer(window)
        return result.predict_next(window)
    raise ValueError("method must be hankel or bm")

def monitor(observations,*,warmup=12,window=16,method="bm",
            alarm_threshold=Fraction(0),reset_on_alarm=True):
    seq=tuple(observations)
    if any(type(x) not in (int,Fraction) for x in seq):
        raise TypeError("exact rational observations required")
    if type(warmup) is not int or warmup<3 or type(window) is not int or window<3:
        raise ValueError("warmup and window must be at least 3")
    if len(seq)<=warmup:raise ValueError("not enough observations")
    if type(alarm_threshold) not in (int,Fraction) or alarm_threshold<0:
        raise ValueError("invalid alarm threshold")
    if type(reset_on_alarm) is not bool:raise TypeError("reset_on_alarm must be bool")
    if method not in ("bm","hankel"):raise ValueError("unknown method")
    events=[];alarms=[];errors=[];covered=0;exact=0
    start=0
    for n in range(warmup,len(seq)):
        train_start=max(start,n-window)
        history=seq[train_start:n]
        predicted=_fit_predict(history,method) if len(history)>=3 else None
        actual=Fraction(seq[n])
        mismatch=None if predicted is None else predicted!=actual
        alarm=predicted is not None and abs(predicted-actual)>alarm_threshold
        if predicted is not None:
            covered+=1;exact+=int(not mismatch);errors.append(abs(predicted-actual))
        events.append(Event(n,actual,predicted,method,mismatch,alarm,train_start))
        if alarm:
            alarms.append(n)
            if reset_on_alarm:start=n if reset_on_alarm else start
    return OnlineResult(tuple(events),tuple(alarms),covered,exact,tuple(errors))

def metrics(result):
    total=len(result.events)
    return {"evaluated":total,"covered":result.covered,"exact":result.exact,
            "coverage":Fraction(result.covered,total),
            "exact_rate_covered":Fraction(result.exact,result.covered) if result.covered else None,
            "mae_covered":sum(result.errors,Fraction(0))/result.covered if result.covered else None,
            "alarms":result.alarms}
