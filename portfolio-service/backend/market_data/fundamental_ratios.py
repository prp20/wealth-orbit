"""Compute latest fundamental ratios from stored statements (calc_v1).

Computed values win over Screener ``#top-ratios`` fallback. Trends (YoY/QoQ) are
built on read from statement history and are not persisted as a time series.
"""
from __future__ import annotations

import math
import re
from typing import Any

from .daily_metrics import _as_float, _metric_number
from .latest_snapshot import prune_non_latest_metric_dates

CALC_VERSION = "calc_v1"
CONSOLIDATED = "CONSOLIDATED"
STANDALONE = "STANDALONE"

# ``stock_daily_metrics.roce`` / ``.roe`` and bag ``ratios.ROCE`` / ``ratios.ROE`` use fractions.
_FRACTION_RATIO_CODES = frozenset({"ROE", "ROCE"})

# Screener #top-ratios label → canonical ratio code (fill gaps only).
TOP_RATIOS_FALLBACK = {
    "ROE": "ROE",
    "ROCE": "ROCE",
    "Debt to equity": "DEBT_TO_EQUITY",
    "Debt to Equity": "DEBT_TO_EQUITY",
    "Interest Coverage": "INTEREST_COVERAGE",
    "Current Ratio": "CURRENT_RATIO",
    "Quick Ratio": "QUICK_RATIO",
    "Asset Turnover": "ASSET_TURNOVER",
    "ROA": "ROA",
    "NPM": "PAT_MARGIN",
    "OPM": "OPERATING_MARGIN",
    # Profit Var is variance %, not PAT margin — never map it to PAT_MARGIN.
}

RATIO_DEFINITIONS = {
    "ROE": "Net profit / shareholders' equity (calc_v1; Screener fallback when inputs missing)",
    "ROCE": "Operating profit / (equity + borrowings) (calc_v1)",
    "PAT_MARGIN": "Net profit / revenue (calc_v1)",
    "OPERATING_MARGIN": "Operating profit / revenue or Screener OPM (calc_v1)",
    "DEBT_TO_EQUITY": "Borrowings / shareholders' equity (calc_v1)",
    "INTEREST_COVERAGE": "Operating profit / interest expense (calc_v1)",
    "CURRENT_RATIO": "Current assets / current liabilities (Screener fallback when BS lines absent)",
    "QUICK_RATIO": "Quick assets / current liabilities (Screener fallback when BS lines absent)",
    "ASSET_TURNOVER": "Revenue / total assets (calc_v1)",
    "ROA": "Net profit / total assets (calc_v1)",
    "REVENUE_GROWTH": "Period-over-period revenue growth from stored statements (on read)",
    "EPS_GROWTH": "Period-over-period EPS growth from stored statements (on read)",
}


def _finite(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return value


def _div(num: float | None, den: float | None, *, as_percent: bool = False) -> float | None:
    n = _as_float(num)
    d = _as_float(den)
    if n is None or d is None or d == 0:
        return None
    out = n / d
    if as_percent:
        out *= 100
    return _finite(out)


def _equity(period: dict[str, float | None]) -> float | None:
    capital = _as_float(period.get("EQUITY_CAPITAL"))
    reserves = _as_float(period.get("RESERVES"))
    if capital is None and reserves is None:
        return None
    return (capital or 0.0) + (reserves or 0.0)


def calc_v1_from_period(
    period: dict[str, float | None],
    *,
    prior: dict[str, float | None] | None = None,
) -> dict[str, float | None]:
    """Compute ratio snapshot fields for one statement period map (metric_code → value)."""
    revenue = period.get("REVENUE")
    net_profit = period.get("NET_PROFIT")
    operating_profit = period.get("OPERATING_PROFIT")
    interest = period.get("INTEREST_EXPENSE")
    borrowings = period.get("BORROWINGS")
    total_assets = period.get("TOTAL_ASSETS")
    equity = _equity(period)
    # Require equity before ROCE; do not treat missing equity as 0 when only borrowings exist.
    capital_employed = None
    if equity is not None:
        capital_employed = equity + (_as_float(borrowings) or 0.0)

    operating_margin = period.get("OPERATING_MARGIN")
    if operating_margin is None:
        operating_margin = _div(operating_profit, revenue, as_percent=True)

    out: dict[str, float | None] = {
        "ROE": _div(net_profit, equity, as_percent=False),
        "ROCE": _div(operating_profit, capital_employed, as_percent=False),
        "PAT_MARGIN": _div(net_profit, revenue, as_percent=True),
        "OPERATING_MARGIN": _as_float(operating_margin),
        "DEBT_TO_EQUITY": _div(borrowings, equity),
        "INTEREST_COVERAGE": _div(operating_profit, interest),
        "CURRENT_RATIO": None,
        "QUICK_RATIO": None,
        "ASSET_TURNOVER": _div(revenue, total_assets),
        "ROA": _div(net_profit, total_assets, as_percent=True),
        "REVENUE_GROWTH": None,
        "EPS_GROWTH": None,
    }
    if prior:
        out["REVENUE_GROWTH"] = period_growth(period.get("REVENUE"), prior.get("REVENUE"))
        out["EPS_GROWTH"] = period_growth(period.get("EPS"), prior.get("EPS"))
    return out


def period_growth(current: float | None, prior: float | None) -> float | None:
    """Percent change; null when prior missing or zero."""
    cur = _as_float(current)
    prev = _as_float(prior)
    if cur is None or prev is None:
        return None
    return _div(cur - prev, prev, as_percent=True)


def merge_top_ratios_fallback(
    computed: dict[str, float | None],
    top_ratios: dict[str, str] | None,
) -> dict[str, float | None]:
    """Fill only missing computed fields from Screener #top-ratios labels."""
    if not top_ratios:
        return dict(computed)
    merged = dict(computed)
    for label, code in TOP_RATIOS_FALLBACK.items():
        if merged.get(code) is not None:
            continue
        raw = top_ratios.get(label)
        if raw is None:
            continue
        cleaned = re.sub(r"\s*%\s*$", "", str(raw))
        number = _metric_number(cleaned)
        if number is None:
            continue
        if code in _FRACTION_RATIO_CODES:
            number = number / 100.0
        merged[code] = number
    return merged


def periods_by_code(
    rows: list[dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    """Group statement rows into period_end_date → metric_code → value."""
    out: dict[str, dict[str, float | None]] = {}
    for row in rows:
        period = str(row["period_end_date"])[:10]
        code = str(row["metric_code"])
        out.setdefault(period, {})[code] = _as_float(row.get("metric_value"))
    return out


def latest_two_periods(
    by_period: dict[str, dict[str, float | None]],
) -> tuple[str | None, dict[str, float | None], dict[str, float | None] | None]:
    """Return (latest_date, latest_map, prior_map)."""
    if not by_period:
        return None, {}, None
    dates = sorted(by_period.keys(), reverse=True)
    latest = dates[0]
    prior = by_period[dates[1]] if len(dates) > 1 else None
    return latest, by_period[latest], prior


def build_latest_snapshot(
    statement_rows: list[dict[str, Any]],
    top_ratios: dict[str, str] | None = None,
    *,
    reporting_basis: str = CONSOLIDATED,
    reporting_period: str = "ANNUAL",
) -> dict[str, Any]:
    """Build one latest ratio snapshot (consol annual preferred at sync)."""
    by_period = periods_by_code(statement_rows)
    as_of, latest, prior = latest_two_periods(by_period)
    computed = calc_v1_from_period(latest, prior=prior) if as_of else {k: None for k in RATIO_DEFINITIONS}
    ratios = merge_top_ratios_fallback(computed, top_ratios)
    methods = {}
    for code, value in ratios.items():
        if value is None:
            methods[code] = None
        elif computed.get(code) is not None:
            methods[code] = CALC_VERSION
        else:
            methods[code] = "screener_top_ratios"
    return {
        "as_of": as_of,
        "reporting_basis": reporting_basis,
        "reporting_period": reporting_period,
        "calculation_method": CALC_VERSION,
        "ratios": ratios,
        "methods": methods,
    }


def growth_series(
    statement_rows: list[dict[str, Any]],
    metric_code: str,
) -> dict[str, float | None]:
    """On-read YoY/QoQ growth map keyed by period_end_date."""
    by_period = periods_by_code(statement_rows)
    dates = sorted(by_period.keys())
    out: dict[str, float | None] = {}
    for index, date in enumerate(dates):
        if index == 0:
            out[date] = None
            continue
        out[date] = period_growth(
            by_period[date].get(metric_code),
            by_period[dates[index - 1]].get(metric_code),
        )
    return out


def _snapshot_has_ratios(snapshot: dict[str, Any]) -> bool:
    ratios = snapshot.get("ratios") or {}
    return any(value is not None and value != "" for value in ratios.values())


def upsert_latest_fundamental_ratios(cur, stock_id, snapshot: dict[str, Any], source_id) -> str | None:
    """Persist one latest fundamental_ratios bag; delete older daily_metrics rows.

    Prefers the existing newest ``metric_date`` so Yahoo valuation columns stay on
    the same latest row. Falls back to statement ``as_of`` (or today) when no row exists.

    Skips write when the snapshot has no ``as_of`` and no non-null ratios, so a thin
    sync cannot wipe a prior non-empty bag.
    """
    import json
    from datetime import date as date_cls

    from psycopg2.extras import Json

    as_of = snapshot.get("as_of")
    has_ratios = _snapshot_has_ratios(snapshot)
    if not as_of and not has_ratios:
        return None

    cur.execute(
        """
        SELECT metric_date, fundamental_ratios
        FROM market_data.stock_daily_metrics
        WHERE stock_id=%s
        ORDER BY metric_date DESC
        LIMIT 1
        """,
        (stock_id,),
    )
    row = cur.fetchone()
    if row:
        metric_date = row[0]
        prior_bag = row[1] if len(row) > 1 else None
    elif as_of:
        metric_date = as_of
        prior_bag = None
    else:
        metric_date = date_cls.today()
        prior_bag = None

    # Never replace a stored non-empty bag with an empty ratio map.
    if not has_ratios and isinstance(prior_bag, dict):
        prior_ratios = prior_bag.get("ratios") or {}
        if any(value is not None and value != "" for value in prior_ratios.values()):
            return str(metric_date)

    payload = {
        "as_of": snapshot.get("as_of"),
        "reporting_basis": snapshot.get("reporting_basis"),
        "reporting_period": snapshot.get("reporting_period"),
        "calculation_method": snapshot.get("calculation_method"),
        "ratios": snapshot.get("ratios") or {},
        "methods": snapshot.get("methods") or {},
        "updated_at": date_cls.today().isoformat(),
    }
    if isinstance(prior_bag, dict):
        prior_sources = prior_bag.get("provider_metric_sources")
        if isinstance(prior_sources, dict) and prior_sources:
            payload["provider_metric_sources"] = dict(prior_sources)
    # Ensure JSON-serializable floats/None
    json.dumps(payload, allow_nan=False)

    # Column check allows only PROVIDER | CALCULATED; calc_v1 lives in the JSON bag.
    cur.execute(
        """
        INSERT INTO market_data.stock_daily_metrics
          (stock_id, metric_date, fundamental_ratios, calculation_method, source_id)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (stock_id, metric_date) DO UPDATE SET
          fundamental_ratios = EXCLUDED.fundamental_ratios,
          updated_at = NOW()
        -- Do not overwrite Yahoo calculation_method / valuation columns.
        """,
        (stock_id, metric_date, Json(payload), "CALCULATED", source_id),
    )
    prune_non_latest_metric_dates(cur, stock_id, metric_date)
    return str(metric_date)
