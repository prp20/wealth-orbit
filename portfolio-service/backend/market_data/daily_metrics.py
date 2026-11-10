"""Provider mapping and guarded calculation fallbacks for daily valuation metrics."""
from __future__ import annotations

import math
import re

from .providers.screener import normalize_number


PROVIDER_METRIC_LABELS = {
    "Market Cap": "market_cap",
    "Stock P/E": "pe_ratio",
    "Price to Book Value": "pb_ratio",
    "Dividend Yield": "dividend_yield",
    "Book Value": "book_value",
    "ROCE": "roce",
    "ROE": "roe",
}


def provider_metrics_from_ratios(ratios: dict[str, str]) -> tuple[dict[str, float], list[dict[str, str]]]:
    """Map a Screener ratio panel to canonical daily-metric fields without guessing unknown fields."""
    metrics: dict[str, float] = {}
    warnings: list[dict[str, str]] = []
    for label, raw_value in ratios.items():
        target = PROVIDER_METRIC_LABELS.get(label)
        if target is None:
            continue
        number = _metric_number(raw_value)
        if number is None:
            warnings.append({"kind": "invalid_provider_metric", "label": label, "value": raw_value})
        else:
            metrics[target] = number
    return metrics, warnings


def _metric_number(value: str) -> float | None:
    # Screener's market-cap display includes a unit suffix (e.g. "1,25,000 Cr.").
    cleaned = re.sub(r"\s*(?:Cr\.?|₹)\s*$", "", value, flags=re.IGNORECASE)
    return normalize_number(cleaned)


def _as_float(raw) -> float | None:
    """Return a finite float, or None when the value cannot be used in storage."""
    if raw is None or raw == "":
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def net_debt_from_parts(total_debt: float | None, total_cash: float | None) -> float | None:
    """Net debt is debt minus cash. A missing side stays missing; zero is a real amount."""
    debt = _as_float(total_debt)
    cash = _as_float(total_cash)
    if debt is None or cash is None:
        return None
    return debt - cash


# Yahoo NSE (``.NS``) dividendYield is normally a decimal fraction (0.015 = 1.5%).
# Values in [0, 0.2) are treated as that fraction. Values in [0.2, 100] are treated
# as already-percent points so a true 0.8% yield is not scaled to 80%.
_YAHOO_YIELD_FRACTION_MAX = 0.2


def normalize_yahoo_dividend_yield(raw) -> float | None:
    """Store Yahoo dividendYield once as percent points for NSE tickers.

    Rejects negatives, NaN/inf, and nonsense above 100. See ``_YAHOO_YIELD_FRACTION_MAX``.
    """
    number = _as_float(raw)
    if number is None or number < 0:
        return None
    if number < _YAHOO_YIELD_FRACTION_MAX:
        number = number * 100
    if number > 100:
        return None
    return number


def yahoo_daily_metric_fields(info: dict) -> dict:
    """Map Yahoo info to stored daily-metric columns.

    Never stores Yahoo PEG (forward or trailing). Conversion failures become NULL
    fields instead of raising, so sync jobs keep opaque failure tokens.
    """
    market_cap = _as_float(info.get("marketCap"))
    enterprise_value = _as_float(info.get("enterpriseValue"))
    ebitda_ttm = _as_float(info.get("ebitda"))
    net_debt = net_debt_from_parts(info.get("totalDebt"), info.get("totalCash"))
    ev_ebitda = _as_float(info.get("enterpriseToEbitda"))
    if ev_ebitda is None and enterprise_value is not None and ebitda_ttm not in (None, 0):
        ev_ebitda = enterprise_value / ebitda_ttm
    revenue = _as_float(info.get("totalRevenue"))
    ev_sales = _as_float(info.get("enterpriseToRevenue"))
    if ev_sales is None and enterprise_value is not None and revenue not in (None, 0):
        ev_sales = enterprise_value / revenue
    fcf = _as_float(info.get("freeCashflow"))
    fcf_yield = None
    if fcf is not None and market_cap is not None and market_cap > 0:
        fcf_yield = fcf / market_cap * 100
    return {
        "market_cap": market_cap,
        "stock_pe": _as_float(info.get("trailingPE")),
        "price_to_book": _as_float(info.get("priceToBook")),
        "dividend_yield": normalize_yahoo_dividend_yield(info.get("dividendYield")),
        "book_value": _as_float(info.get("bookValue")),
        "roce": _as_float(info.get("returnOnCapitalEmployed")),
        "roe": _as_float(info.get("returnOnEquity")),
        "enterprise_value": enterprise_value,
        "ebitda_ttm": ebitda_ttm,
        "ev_ebitda": ev_ebitda,
        "ev_sales": ev_sales,
        "net_debt": net_debt,
        "fcf_yield": fcf_yield,
        "peg": None,
    }


def calculate_fallback_metrics(
    *, close: float | None, eps: float | None, book_value: float | None, dividend_per_share: float | None,
) -> dict[str, float]:
    """Return only ratios supported by present, non-zero inputs; never fabricate unavailable values."""
    if close is None or close <= 0:
        return {}
    metrics: dict[str, float] = {}
    if eps is not None and eps > 0:
        metrics["pe_ratio"] = close / eps
    if book_value is not None and book_value > 0:
        metrics["pb_ratio"] = close / book_value
    if dividend_per_share is not None and dividend_per_share >= 0:
        metrics["dividend_yield"] = dividend_per_share / close * 100
    return metrics
