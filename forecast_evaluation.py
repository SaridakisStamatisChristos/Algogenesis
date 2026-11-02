"""Leakage-free rolling-origin evaluation of exact recurrence discovery.

At each origin only the preceding training window is used to fit a model.
The subsequent horizon is scored without updating the model with held-out
values. Persistence and last-difference extrapolation are honest baselines.
All errors use exact rational arithmetic; no random split or test leakage.
"""
from dataclasses import dataclass
from fractions import Fraction
from observable_recurrence import synthesize

@dataclass(frozen=True)
class Fold:
    origin:int
    actual:tuple
    recurrence:tuple|None
    persistence:tuple
    linear:tuple
    order:int|None

@dataclass(frozen=True)
class Evaluation:
    folds:tuple[Fold,...]
    recurrence_mae:Fraction|None
    persistence_mae:Fraction
    linear_mae:Fraction
    coverage:Fraction
    evaluated_points:int

def _mae(pairs):
    if not pairs:return None
    return sum((abs(Fraction(a)-Fraction(b)) for a,b in pairs),Fraction(0))/len(pairs)

def evaluate(observations,*,min_train=8,horizon=3,stride=1,
             max_order=None,window=None):
    values=tuple(observations)
    if any(type(v) not in (int,Fraction) for v in values):
        raise TypeError('exact rational observations required')
    if any(type(v) is not int or v<1 for v in (min_train,horizon,stride)):
        raise ValueError('positive evaluation parameters required')
    if min_train<3:raise ValueError('min_train must be at least three')
    if window is not None and (type(window) is not int or window<min_train):
        raise ValueError('window must be at least min_train')
    if max_order is not None and (type(max_order) is not int or max_order<1):
        raise ValueError('invalid order budget')
    if len(values)<min_train+horizon:raise ValueError('insufficient observations for a fold')
    folds=[]
    for origin in range(min_train,len(values)-horizon+1,stride):
        train=values[:origin] if window is None else values[max(0,origin-window):origin]
        actual=values[origin:origin+horizon]
        fit=synthesize(train,max_order=max_order)
        if fit.model is None:
            predicted=None
        else:
            # The recurrence starts at the beginning of the training window.
            predicted=fit.model.generate(len(train)+horizon)[-horizon:]
        last=train[-1]
        difference=train[-1]-train[-2]
        persistence=(last,)*horizon
        linear=tuple(last+difference*(j+1) for j in range(horizon))
        folds.append(Fold(origin,actual,predicted,persistence,linear,fit.order))
    rec_pairs=[(a,b) for f in folds if f.recurrence is not None
               for a,b in zip(f.actual,f.recurrence)]
    base_pairs=[(a,b) for f in folds for a,b in zip(f.actual,f.persistence)]
    linear_pairs=[(a,b) for f in folds for a,b in zip(f.actual,f.linear)]
    total=sum(len(f.actual) for f in folds)
    return Evaluation(tuple(folds),_mae(rec_pairs),_mae(base_pairs),
                      _mae(linear_pairs),Fraction(len(rec_pairs),total),total)

def report(evaluation):
    """Machine-readable exact metric summary with abstention explicit."""
    return {
        'folds':len(evaluation.folds),
        'points':evaluation.evaluated_points,
        'coverage':str(evaluation.coverage),
        'recurrence_mae':None if evaluation.recurrence_mae is None else str(evaluation.recurrence_mae),
        'persistence_mae':str(evaluation.persistence_mae),
        'linear_mae':str(evaluation.linear_mae),
    }
