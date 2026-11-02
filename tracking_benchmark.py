"""Causal real-world baselines: fixed-weight experts, Fixed Share, ARIMA/SES/Holt.

Statsmodels is optional. Statistical model parameters fit once on the first
32 samples. Every later forecast precedes observing that sample.
"""
from fractions import Fraction
from time import perf_counter_ns
from regret_forecast import BoundedExperts,causal_candidates,EXPERTS
from switching_experts import FixedShareExperts,tuned_tracking_parameters
from regret_benchmark import historical_series,HISTORICAL_CONFIG

def compare(series,*,lower,upper,season=11,warmup=32,
            share=None,max_switches=2,with_arima=False,with_ets=False):
    values=tuple(series)
    if type(warmup) is not int or warmup<32 or len(values)<=warmup:
        raise ValueError("warmup must leave test suffix")
    if type(max_switches) is not int or max_switches<0:raise ValueError("invalid switch budget")
    eta,auto_share=tuned_tracking_parameters(len(values)-warmup,len(EXPERTS),max_switches)
    if share is None:share=auto_share
    kw=dict(lower=lower,upper=upper,eta=eta)
    fixed=BoundedExperts(EXPERTS,**kw)
    tracking=FixedShareExperts(EXPERTS,share=share,**kw)
    arima=None;arima_initial_fit_converged=None;arima_preds=[]
    ets_models={};ets_predictions={}
    if with_arima:
        try:from statsmodels.tsa.statespace.sarimax import SARIMAX
        except ImportError as e:raise RuntimeError("statsmodels needed for ARIMA") from e
        arima=SARIMAX([float(v) for v in values[:warmup]],order=(1,1,0),trend="n",
                      enforce_stationarity=False,enforce_invertibility=False).fit(disp=False)
        arima_initial_fit_converged=bool(arima.mle_retvals.get("converged",True))
    if with_ets:
        try:from statsmodels.tsa.holtwinters import SimpleExpSmoothing,Holt
        except ImportError as e:raise RuntimeError("statsmodels needed for ETS") from e
        prefix=[float(v) for v in values[:warmup]]
        for method,cls in (("ses",SimpleExpSmoothing),("holt",Holt)):
            fitted=cls(prefix,initialization_method="estimated").fit(optimized=True)
            ets_models[method]={
                "level":float(fitted.level[-1]),
                "trend":float(fitted.trend[-1]) if method=="holt" else 0.0,
                "alpha":float(fitted.params["smoothing_level"]),
                "beta":float(fitted.params["smoothing_trend"]) if method=="holt" else 0.0}
            ets_predictions[method]=[]
    start=perf_counter_ns()
    for t in range(warmup,len(values)):
        candidates=causal_candidates(values[:t],season=season)
        fixed.predict(candidates);tracking.predict(candidates)
        if arima is not None:arima_preds.append(float(arima.forecast(1)[0]))
        for method,model in ets_models.items():
            old_level=model["level"];old_trend=model["trend"]
            predicted=old_level+old_trend
            ets_predictions[method].append(predicted)
            model["level"]=model["alpha"]*float(values[t])+(1-model["alpha"])*predicted
            if method=="holt":
                model["trend"]=model["beta"]*(model["level"]-old_level)+(1-model["beta"])*old_trend
        fixed.observe(values[t]);tracking.observe(values[t])
        if arima is not None:arima=arima.extend([float(values[t])])
    elapsed=perf_counter_ns()-start
    t=len(values)-warmup
    fixed_mae=sum((abs(r.prediction-r.actual) for r in fixed.records),Fraction(0))/t
    tracking_mae=sum((abs(r.prediction-r.actual) for r in tracking.records),Fraction(0))/t
    naive_mae=sum((abs(values[i]-values[i-1]) for i in range(warmup,len(values))),Fraction(0))/t
    path=tracking.best_switching_path(max_switches)
    cert=tracking.switching_certificate(path)
    result={
        "n":t,"eta":str(eta),"share":str(share),"max_switches":max_switches,
        "fixed_mae":float(fixed_mae),"tracking_mae":float(tracking_mae),
        "persistence_mae":float(naive_mae),
        "best_switch_path_mae":float(cert.comparator_loss*(upper-lower)/t),
        "switches_in_best_path":cert.switches,"normalized_regret":float(cert.regret),
        "normalized_regret_bound":float(cert.bound),"certificate_valid":cert.valid,
        "forecast_elapsed_ns":elapsed}
    if arima is not None:
        result["arima_110_mae"]=sum(abs(a-b) for a,b in zip(arima_preds,map(float,values[warmup:])))/t
        result["arima_initial_fit_converged"]=arima_initial_fit_converged
    for name,preds in ets_predictions.items():
        result[name+"_mae"]=sum(abs(a-b) for a,b in zip(preds,map(float,values[warmup:])))/t
    return result

def benchmark_historical(*,with_arima=True,with_ets=True):
    return {name:compare(seq,lower=HISTORICAL_CONFIG[name][0],
                         upper=HISTORICAL_CONFIG[name][1],
                         season=HISTORICAL_CONFIG[name][2],
                         with_arima=with_arima,with_ets=with_ets)
            for name,seq in historical_series().items()}

if __name__=="__main__":
    import json
    print(json.dumps(benchmark_historical(),indent=2,sort_keys=True))
