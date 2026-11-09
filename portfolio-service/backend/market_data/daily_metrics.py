"""Provider mapping and guarded calculation fallbacks for daily valuation metrics."""
from __future__ import annotations

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


def net_debt_from_parts(total_debt: float | None, total_cash: float | None) -> float | None:
    """Net debt is debt minus cash. A missing side stays missing; zero is a real amount."""
    if total_debt is None or total_cash is None:
        return None
    return float(total_debt) - float(total_cash)


def normalize_yahoo_dividend_yield(raw) -> float | None:
    """Store Yahoo dividendYield once as percent points.

    Yahoo may return a fraction (0.015) or already-percent (1.5). Values already
    in a sane percent range stay as-is. Nonsense outside 0–100 is rejected.
    """
    if raw is None or raw == "":
        return None
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    if number < 1.0:
        number = number * 100
    if number > 100:
        return None
    return number


def yahoo_daily_metric_fields(info: dict) -> dict:
    """Map Yahoo info to stored daily-metric columns. Never reads forward PEG."""
    market_cap = info.get("marketCap")
    enterprise_value = info.get("enterpriseValue")
    ebitda_ttm = info.get("ebitda")
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    net_debt = net_debt_from_parts(total_debt, total_cash)
    ev_ebitda = info.get("enterpriseToEbitda")
    if ev_ebitda is None and enterprise_value and ebitda_ttm and float(ebitda_ttm) != 0:
        ev_ebitda = float(enterprise_value) / float(ebitda_ttm)
    revenue = info.get("totalRevenue")
    ev_sales = info.get("enterpriseToRevenue")
    if ev_sales is None and enterprise_value and revenue and float(revenue) != 0:
        ev_sales = float(enterprise_value) / float(revenue)
    fcf = info.get("freeCashflow")
    fcf_yield = None
    if fcf is not None and market_cap and float(market_cap) > 0:
        fcf_yield = float(fcf) / float(market_cap) * 100
    return {
        "market_cap": market_cap,
        "stock_pe": info.get("trailingPE"),
        "price_to_book": info.get("priceToBook"),
        "dividend_yield": normalize_yahoo_dividend_yield(info.get("dividendYield")),
        "book_value": info.get("bookValue"),
        "roce": info.get("returnOnCapitalEmployed"),
        "roe": info.get("returnOnEquity"),
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
