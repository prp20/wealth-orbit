"""Pure, dependency-light daily technical indicator calculations."""
from __future__ import annotations
import json
import pandas as pd

def normalize_parameters(parameters: dict | None = None) -> str:
    return json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"))

def calculate_indicators(frame: pd.DataFrame, requests: list[dict]) -> pd.DataFrame:
    """Return long-form indicator rows. Frame must contain date and close."""
    if frame.empty: return pd.DataFrame(columns=["date","indicator_code","indicator_period","parameters","component","value"])
    data = frame.sort_values("date").reset_index(drop=True).copy()
    close = pd.to_numeric(data["close"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce") if "high" in data.columns else close
    low = pd.to_numeric(data["low"], errors="coerce") if "low" in data.columns else close
    out = []
    for req in requests:
        code = req["code"].upper(); p = req.get("parameters") or {}; period = int(p.get("period", 0))
        series = {}
        if code == "SMA": series["VALUE"] = close.rolling(period).mean()
        elif code == "EMA": series["VALUE"] = close.ewm(span=period, adjust=False, min_periods=period).mean()
        elif code == "RSI":
            delta = close.diff(); gain = delta.clip(lower=0); loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean(); avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
            rs = avg_gain / avg_loss.replace(0, pd.NA); series["VALUE"] = 100 - (100 / (1 + rs))
        elif code == "MACD":
            fast, slow, signal = int(p.get("fast",12)), int(p.get("slow",26)), int(p.get("signal",9))
            line = close.ewm(span=fast, adjust=False, min_periods=fast).mean() - close.ewm(span=slow, adjust=False, min_periods=slow).mean()
            sig = line.ewm(span=signal, adjust=False, min_periods=signal).mean(); series = {"VALUE":line,"SIGNAL":sig,"HISTOGRAM":line-sig}; period = slow
        elif code == "BB":
            period = int(p.get("period",20)); std = float(p.get("std_dev",2)); mid = close.rolling(period).mean(); band = close.rolling(period).std(ddof=0)*std
            series = {"UPPER":mid+band,"MIDDLE":mid,"LOWER":mid-band}
        elif code == "ATR":
            period = int(p.get("period", 14))
            prev_close = close.shift(1)
            tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
            series["VALUE"] = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
        else: raise ValueError(f"Unsupported indicator: {code}")
        params = normalize_parameters(p)
        for component, values in series.items():
            for i, value in enumerate(values):
                out.append({"date": data.loc[i,"date"], "indicator_code": code, "indicator_period": period, "parameters": params, "component": component, "value": None if pd.isna(value) else float(value)})
    return pd.DataFrame(out)
