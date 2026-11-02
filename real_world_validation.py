"""Optional historical data validation. Requires statsmodels only when invoked.

Evaluate Nile 1871-1970 and sunspots 1700-2008 using causal, one-step
prequential evaluation and identical targets for each predictor.
"""
import json
from fractions import Fraction
from math import isfinite
from adaptive_forecast import evaluate


def numeric_series(values):
    seq=[]
    for value in values:
        if type(value) is bool:
            raise TypeError("booleans are not observations")
        if isinstance(value,Fraction):
            seq.append(value)
        elif isinstance(value,(int,float)):
            if not isfinite(value):raise ValueError("observations must be finite")
            seq.append(Fraction(str(value)))
        else:
            if not hasattr(value,"item"):raise TypeError("numeric observations required")
            primitive=value.item()
            if type(primitive) not in (int,float):
                raise TypeError("real observations required")
            if not isfinite(primitive):raise ValueError("observations must be finite")
            seq.append(Fraction(str(primitive)))
    return tuple(seq)


def evaluate_series(values,*,period=11):
    if type(period) is not int or period<1 or period>32:
        raise ValueError("period must be in [1,32]")
    seq=numeric_series(values)
    result=evaluate(seq)
    n=len(result.records)
    seasonal=sum((abs(seq[r.index-period]-r.observed)/(1+abs(r.observed))
                  for r in result.records),Fraction(0))/n
    errors={"adaptive":float(result.selected_relative_mae),
            **{name:float(error) for name,error in result.candidate_relative_mae},
            f"seasonal_naive_{period}":float(seasonal)}
    return {"observations":len(seq),"evaluated":n,"switches":result.switches,
            "mean_relative_error":errors}


def run_statsmodels():
    try:
        import statsmodels
        from statsmodels.datasets import nile,sunspots
    except ImportError as exc:
        raise RuntimeError("optional dependency: pip install statsmodels==0.14.6") from exc
    return {"statsmodels_version":statsmodels.__version__,"datasets":{
        "nile_annual_flow_1871_1970":evaluate_series(nile.load_pandas().data["volume"]),
        "annual_sunspots_1700_2008":evaluate_series(sunspots.load_pandas().data["SUNACTIVITY"]),
    }}


if __name__=="__main__":
    print(json.dumps(run_statsmodels(),sort_keys=True,indent=2))
