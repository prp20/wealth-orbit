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
