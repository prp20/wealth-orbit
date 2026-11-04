"""Pure mutual-fund return and risk calculations."""
from __future__ import annotations

from datetime import timedelta
import math
import numpy as np
import pandas as pd


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.date
    result["nav"] = pd.to_numeric(result["nav"], errors="coerce")
    return result.dropna(subset=["date", "nav"]).query("nav > 0").sort_values("date").drop_duplicates("date")


def _prior(frame: pd.DataFrame, target) -> pd.Series | None:
    candidates = frame[frame["date"] <= target]
    return None if candidates.empty else candidates.iloc[-1]


PERIOD_DAYS = {"1M": 30, "3M": 91, "6M": 182}
YEAR_PERIODS = {"1Y": 1, "3Y": 3, "5Y": 5, "10Y": 10}
METRIC_PERIODS = ("1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y")


def trailing_return(frame: pd.DataFrame, years: int) -> float | None:
    return trailing_return_days(frame, int(round(365.25 * years)))


def trailing_return_days(frame: pd.DataFrame, days: int) -> float | None:
    data = _clean(frame)
    if data.empty or days <= 0:
        return None
    end = data.iloc[-1]
    start = _prior(data, end["date"] - timedelta(days=days))
    if start is None or start["date"] >= end["date"]:
        return None
    return float(end["nav"] / start["nav"] - 1)


def cagr(frame: pd.DataFrame, years: int) -> float | None:
    data = _clean(frame)
    if data.empty:
        return None
    end = data.iloc[-1]
    start = _prior(data, end["date"] - timedelta(days=365.25 * years))
    if start is None or start["date"] >= end["date"]:
        return None
    elapsed = (end["date"] - start["date"]).days / 365.25
    return float((end["nav"] / start["nav"]) ** (1 / elapsed) - 1)


def daily_returns(frame: pd.DataFrame) -> pd.Series:
    data = _clean(frame)
    return data["nav"].pct_change().dropna()


def rolling_returns(frame: pd.DataFrame, years: int) -> pd.Series:
    data = _clean(frame)
    values = []
    for _, end in data.iterrows():
        start = _prior(data, end["date"] - timedelta(days=365.25 * years))
        if start is not None and start["date"] < end["date"]:
            elapsed = (end["date"] - start["date"]).days / 365.25
            values.append((end["date"], float((end["nav"] / start["nav"]) ** (1 / elapsed) - 1)))
    return pd.Series(dict(values), dtype=float)


def annualized_stddev(returns: pd.Series, factor: int = 252) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    return None if len(values) < 2 else float(values.std(ddof=1) * math.sqrt(factor))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, factor: int = 252) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    std = annualized_stddev(values, factor)
    if std in (None, 0):
        return None
    return float((values.mean() * factor - risk_free_rate) / std)


def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.0, factor: int = 252) -> float | None:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    downside = values[values < 0]
    if downside.empty:
        return None
    deviation = float(downside.std(ddof=0) * math.sqrt(factor))
    return None if deviation == 0 else float((values.mean() * factor - risk_free_rate) / deviation)


def max_drawdown(frame: pd.DataFrame) -> float | None:
    data = _clean(frame)
    if data.empty:
        return None
    drawdowns = data["nav"] / data["nav"].cummax() - 1
    return float(drawdowns.min())


def aligned_returns(fund: pd.DataFrame, benchmark: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    left = _clean(fund)[["date", "nav"]].rename(columns={"nav": "fund"})
    right = _clean(benchmark)[["date", "nav"]].rename(columns={"nav": "benchmark"})
    joined = left.merge(right, on="date", how="inner").sort_values("date")
    return joined["fund"].pct_change().dropna(), joined["benchmark"].pct_change().dropna()


def alpha_beta(fund_returns: pd.Series, benchmark_returns: pd.Series, risk_free_rate: float = 0.0, factor: int = 252) -> tuple[float | None, float | None]:
    joined = pd.concat([fund_returns, benchmark_returns], axis=1).dropna()
    if len(joined) < 2 or float(joined.iloc[:, 1].var(ddof=1)) == 0:
        return None, None
    beta = float(joined.iloc[:, 0].cov(joined.iloc[:, 1]) / joined.iloc[:, 1].var(ddof=1))
    fund = float((1 + joined.iloc[:, 0]).prod() ** (factor / len(joined)) - 1)
    bench = float((1 + joined.iloc[:, 1]).prod() ** (factor / len(joined)) - 1)
    alpha = fund - (risk_free_rate + beta * (bench - risk_free_rate))
    return float(alpha), beta


def metric_snapshot(nav: pd.DataFrame, benchmark: pd.DataFrame | None = None, risk_free_rate: float = 0.0) -> dict:
    returns = daily_returns(nav)
    result = {"current_nav": float(_clean(nav).iloc[-1]["nav"]) if not _clean(nav).empty else None,
              "standard_deviation": annualized_stddev(returns), "sharpe": sharpe_ratio(returns, risk_free_rate),
              "sortino": sortino_ratio(returns, risk_free_rate), "maximum_drawdown": max_drawdown(nav),
              "observations": len(_clean(nav)), "risk_free_rate": risk_free_rate, "available": not _clean(nav).empty}
    for years in (1, 3, 5, 10):
        result[f"trailing_{years}y"] = trailing_return(nav, years)
        rolling = rolling_returns(nav, years)
        result[f"rolling_{years}y_latest"] = float(rolling.iloc[-1]) if not rolling.empty else None
    if benchmark is not None:
        fund_returns, benchmark_returns = aligned_returns(nav, benchmark)
        alpha, beta = alpha_beta(fund_returns, benchmark_returns, risk_free_rate)
        result.update({"alpha": alpha, "beta": beta, "aligned_observations": len(fund_returns)})
    else:
        result.update({"alpha": None, "beta": None, "aligned_observations": 0})
    return result
