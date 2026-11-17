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

# Mapped provider keys → ``stock_daily_metrics`` column names.
PROVIDER_METRIC_COLUMNS = {
    "market_cap": "market_cap",
    "pe_ratio": "stock_pe",
    "pb_ratio": "price_to_book",
    "dividend_yield": "dividend_yield",
    "book_value": "book_value",
    "roce": "roce",
    "roe": "roe",
}

SCREENER_PROVIDER_SOURCE = "screener"

# Yahoo sync fills these; when Yahoo is NULL, keep the latest stored row (e.g. Screener).
YAHOO_MERGE_PRESERVE_COLUMNS = (
    "market_cap",
    "stock_pe",
    "price_to_book",
    "dividend_yield",
    "book_value",
    "roce",
    "roe",
)

# Screen snapshot stores profitability ratios as fractions (0.139 = 13.9%).
_SCREENER_FRACTION_METRIC_KEYS = frozenset({"roce", "roe"})


def merge_yahoo_daily_fields(
    yahoo: dict[str, float | None],
    prior: dict[str, float | None] | None,
) -> dict[str, float | None]:
    """Keep non-null provider metrics on the latest row when Yahoo omits them."""
    merged = dict(yahoo)
    if not prior:
        return merged
    for key in YAHOO_MERGE_PRESERVE_COLUMNS:
        if merged.get(key) is None and prior.get(key) is not None:
            merged[key] = prior[key]
    return merged


def provider_metrics_from_ratios(ratios: dict[str, str]) -> tuple[dict[str, float], list[dict[str, str]]]:
    """Map a Screener ratio panel to canonical daily-metric fields without guessing unknown fields."""
    metrics: dict[str, float] = {}
    warnings: list[dict[str, str]] = []
    for label, raw_value in ratios.items():
        target = PROVIDER_METRIC_LABELS.get(label)
        if target is None:
            continue
        number = _metric_number(raw_value, label=label)
        if number is None:
            warnings.append({"kind": "invalid_provider_metric", "label": label, "value": raw_value})
        else:
            if target in _SCREENER_FRACTION_METRIC_KEYS:
                number = number / 100.0
            metrics[target] = number
    return metrics, warnings


def merge_screener_provider_fields(
    existing: dict[str, float | None],
    screener: dict[str, float],
) -> tuple[dict[str, float | None], list[str]]:
    """Fill only NULL provider metric columns; never overwrite Yahoo/provider values."""
    merged = dict(existing)
    filled: list[str] = []
    for key, value in screener.items():
        column = PROVIDER_METRIC_COLUMNS.get(key)
        if column is None:
            continue
        if merged.get(column) is None and value is not None:
            merged[column] = value
            filled.append(column)
    return merged, filled


def upsert_screener_provider_metrics(
    cur,
    stock_id,
    ratios: dict[str, str],
    source_id,
    *,
    metric_date_fallback=None,
) -> str | None:
    """Persist Screener ``#ratios`` / ``#top-ratios`` onto the single latest metrics row."""
    from datetime import date as date_cls

    from .latest_snapshot import prune_non_latest_metric_dates

    provider_values, _warnings = provider_metrics_from_ratios(ratios)
    if not provider_values:
        return None

    cur.execute(
        """
        SELECT metric_date, market_cap, stock_pe, price_to_book, dividend_yield, book_value, roce, roe,
               fundamental_ratios
        FROM market_data.stock_daily_metrics
        WHERE stock_id=%s
        ORDER BY metric_date DESC
        LIMIT 1
        """,
        (stock_id,),
    )
    row = cur.fetchone()
    prior = {
        "market_cap": None,
        "stock_pe": None,
        "price_to_book": None,
        "dividend_yield": None,
        "book_value": None,
        "roce": None,
        "roe": None,
    }
    prior_bag = None
    if row:
        metric_date = row[0]
        prior = {
            "market_cap": row[1],
            "stock_pe": row[2],
            "price_to_book": row[3],
            "dividend_yield": row[4],
            "book_value": row[5],
            "roce": row[6],
            "roe": row[7],
        }
        prior_bag = row[8] if len(row) > 8 else None
    else:
        metric_date = metric_date_fallback or date_cls.today()

    merged, filled_columns = merge_screener_provider_fields(prior, provider_values)
    if not filled_columns and row:
        prune_non_latest_metric_dates(cur, stock_id, metric_date)
        return str(metric_date)

    bag = dict(prior_bag) if isinstance(prior_bag, dict) else {}
    if filled_columns:
        sources = dict(bag.get("provider_metric_sources") or {})
        for column in filled_columns:
            sources[column] = SCREENER_PROVIDER_SOURCE
        bag["provider_metric_sources"] = sources

    from psycopg2.extras import Json

    if row:
        cur.execute(
            """
            UPDATE market_data.stock_daily_metrics
            SET market_cap=%s, stock_pe=%s, price_to_book=%s, dividend_yield=%s,
                book_value=%s, roce=%s, roe=%s,
                fundamental_ratios=CASE
                    WHEN %s::jsonb IS NOT NULL THEN COALESCE(fundamental_ratios, '{}'::jsonb) || %s::jsonb
                    ELSE fundamental_ratios
                END,
                updated_at=NOW()
            WHERE stock_id=%s AND metric_date=%s
            """,
            (
                merged["market_cap"],
                merged["stock_pe"],
                merged["price_to_book"],
                merged["dividend_yield"],
                merged["book_value"],
                merged["roce"],
                merged["roe"],
                Json(bag) if bag else None,
                Json(bag) if bag else None,
                stock_id,
                metric_date,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO market_data.stock_daily_metrics
              (stock_id, metric_date, market_cap, stock_pe, price_to_book, dividend_yield,
               book_value, roce, roe, calculation_method, source_id, fundamental_ratios)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PROVIDER',%s,%s)
            """,
            (
                stock_id,
                metric_date,
                merged["market_cap"],
                merged["stock_pe"],
                merged["price_to_book"],
                merged["dividend_yield"],
                merged["book_value"],
                merged["roce"],
                merged["roe"],
                source_id,
                Json(bag) if bag else None,
            ),
        )
    prune_non_latest_metric_dates(cur, stock_id, metric_date)
    return str(metric_date)


def _screener_market_cap_is_crores(value: str) -> bool:
    return bool(re.search(r"\bCr\.?", value, flags=re.IGNORECASE))


def _metric_number(value: str, *, label: str | None = None) -> float | None:
    # Screener's market-cap display includes a unit suffix (e.g. "1,25,000 Cr.").
    is_crores = label == "Market Cap" and _screener_market_cap_is_crores(value)
    cleaned = re.sub(r"\s*(?:Cr\.?|₹)\s*$", "", value, flags=re.IGNORECASE)
    number = normalize_number(cleaned)
    if number is None:
        return None
    if is_crores:
        number *= 10_000_000
    return number


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
