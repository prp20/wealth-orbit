from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import date
import math

@dataclass(frozen=True)
class PricePoint:
    trading_date: date
    close: float

@dataclass(frozen=True)
class IndicatorRequest:
    indicator_code: str
    period: int | None = None
    parameters: dict | None = None
    def normalized(self):
        code = self.indicator_code.upper(); p = dict(self.parameters or {})
        if code == "MACD":
            fast, slow = int(p.get("fast", p.get("fast_period", 12))), int(p.get("slow", p.get("slow_period", 26)))
            if fast >= slow: raise ValueError("fast_period must be less than slow_period")
            p = {"fast": fast, "slow": slow, "signal": int(p.get("signal", p.get("signal_period", 9)))}
        elif code in {"BOLLINGER", "BB"}: p = {"period": int(self.period or p.get("period", 20)), "stddev": float(p.get("stddev", p.get("std_dev", 2)))}
        else: p = {"period": int(self.period or p.get("period", 14 if code == "RSI" else 20))}
        return IndicatorRequest("BB" if code == "BOLLINGER" else code, p.get("period"), p)

@dataclass(frozen=True)
class IndicatorResult:
    trading_date: date
    component: str
    value: float

def canonical_json_parameters(parameters: dict) -> str:
    normalized = {k: (int(v) if isinstance(v, float) and v.is_integer() else v) for k, v in parameters.items()}
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def calculate_indicators(prices: list[PricePoint], request: IndicatorRequest) -> list[IndicatorResult]:
    req = request.normalized(); points = sorted(prices, key=lambda p: p.trading_date); closes = [float(p.close) for p in points]; p = req.parameters or {}; code = req.indicator_code
    series: dict[str,list[float|None]] = {}
    def sma(period): return [None if i+1<period else sum(closes[i-period+1:i+1])/period for i in range(len(closes))]
    def ema(period):
        out=[None]*len(closes); alpha=2/(period+1); value=None
        for i,x in enumerate(closes):
            if i+1==period: value=sum(closes[:period])/period; out[i]=value
            elif i+1>period: value=alpha*x+(1-alpha)*value; out[i]=value
        return out
    if code == "SMA": series["VALUE"] = sma(req.period or 20)
    elif code == "EMA": series["VALUE"] = ema(req.period or 20)
    elif code == "RSI":
        period=req.period or 14; gains=[0.0]+[max(0,closes[i]-closes[i-1]) for i in range(1,len(closes))]; losses=[0.0]+[max(0,closes[i-1]-closes[i]) for i in range(1,len(closes))]; avg_g=[None]*len(closes); avg_l=[None]*len(closes)
        if len(closes)>period: avg_g[period]=sum(gains[1:period+1])/period; avg_l[period]=sum(losses[1:period+1])/period
        for i in range(period+1,len(closes)): avg_g[i]=(avg_g[i-1]*(period-1)+gains[i])/period; avg_l[i]=(avg_l[i-1]*(period-1)+losses[i])/period
        series["VALUE"]=[None if i<period or avg_g[i] is None else (100.0 if avg_l[i]==0 else 100-100/(1+avg_g[i]/avg_l[i])) for i in range(len(closes))]
    elif code == "MACD":
        fast,slow,signal=int(p["fast"]),int(p["slow"]),int(p["signal"]); line=[None if a is None or b is None else a-b for a,b in zip(ema(fast),ema(slow))]; vals=[x for x in line if x is not None]; sig_full=[None]*len(line); e= None
        start=next((i for i,x in enumerate(line) if x is not None),len(line));
        if len(vals)>=signal:
            e=sum(vals[:signal])/signal; sig_full[start+signal-1]=e; alpha=2/(signal+1)
            for i in range(start+signal,len(line)): e=alpha*line[i]+(1-alpha)*e; sig_full[i]=e
        series={"VALUE":line,"SIGNAL":sig_full,"HISTOGRAM":[None if a is None or b is None else a-b for a,b in zip(line,sig_full)]}
    elif code == "BB":
        period=int(p["period"]); sd=float(p["stddev"]); mid=sma(period); upper=[]; lower=[]
        for i,m in enumerate(mid):
            if m is None: upper.append(None); lower.append(None)
            else: d=math.sqrt(sum((x-m)**2 for x in closes[i-period+1:i+1])/period); upper.append(m+sd*d); lower.append(m-sd*d)
        series={"UPPER":upper,"MIDDLE":mid,"LOWER":lower}
    else: raise ValueError(f"Unsupported indicator: {code}")
    if code == "MACD":
        last = max((i for values in series.values() for i,v in enumerate(values) if v is not None), default=-1)
        return [IndicatorResult(points[last].trading_date,c,values[last]) for c,values in series.items() if last >= 0 and values[last] is not None]
    return [IndicatorResult(points[i].trading_date,c,v) for c,values in series.items() for i,v in enumerate(values) if v is not None]
