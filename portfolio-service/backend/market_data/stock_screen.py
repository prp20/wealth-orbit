"""Stock screener snapshot + identity filters over stored metrics only."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from backend.reference_service import _query


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _records_json_safe(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    rows = frame.astype(object).where(pd.notnull(frame), None).to_dict(orient="records")
    return [{key: _json_safe(val) for key, val in row.items()} for row in rows]

# Columns plugins and the results grid may use. Keep docs/screens/README.md in sync.
SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "trading_symbol",
    "company_name",
    "exchange",
    "sector_name",
    "industry_name",
    "market_cap_class",
    "price_close",
    "market_cap",
    "stock_pe",
    "price_to_book",
    "dividend_yield",
    "book_value",
    "roce",
    "roe",
    "enterprise_value",
    "ebitda_ttm",
    "ev_ebitda",
    "ev_sales",
    "net_debt",
    "fcf_yield",
    "peg",
    "metrics_date",
)

STOCK_SCREEN_SORT_COLUMNS = {
    "trading_symbol": "trading_symbol",
    "company_name": "company_name",
    "sector_name": "sector_name",
    "industry_name": "industry_name",
    "market_cap": "market_cap",
    "stock_pe": "stock_pe",
    "price_to_book": "price_to_book",
    "dividend_yield": "dividend_yield",
    "roe": "roe",
    "roce": "roce",
    "ev_ebitda": "ev_ebitda",
    "price_close": "price_close",
}


def build_stock_metrics_snapshot(*, require_metrics: bool = False) -> pd.DataFrame:
    """Latest identity + daily metrics (+ latest close) for active stocks."""
    frame = _query(
        """
        WITH base AS (
          SELECT s.stock_id, s.trading_symbol, s.company_name, s.exchange,
                 s.market_cap_class, sr.sector_name, ir.industry_name
          FROM market_data.stock_reference s
          LEFT JOIN market_data.sector_reference sr ON sr.sector_id = s.sector_id
          LEFT JOIN market_data.industry_reference ir ON ir.industry_id = s.industry_id
          WHERE s.is_active = TRUE
        ),
        latest_metrics AS (
          SELECT DISTINCT ON (m.stock_id)
                 m.stock_id, m.metric_date AS metrics_date,
                 m.market_cap, m.stock_pe, m.price_to_book, m.dividend_yield,
                 m.book_value, m.roce, m.roe, m.enterprise_value, m.ebitda_ttm,
                 m.ev_ebitda, m.ev_sales, m.net_debt, m.fcf_yield, m.peg
          FROM market_data.stock_daily_metrics m
          JOIN base b ON b.stock_id = m.stock_id
          ORDER BY m.stock_id, m.metric_date DESC
        ),
        latest_price AS (
          SELECT DISTINCT ON (p.stock_id)
                 p.stock_id, COALESCE(p.adj_close, p.close) AS price_close
          FROM market_data.stock_daily_prices p
          JOIN base b ON b.stock_id = p.stock_id
          ORDER BY p.stock_id, p.trading_date DESC
        )
        SELECT b.trading_symbol, b.company_name, b.exchange, b.sector_name, b.industry_name,
               b.market_cap_class, lp.price_close,
               lm.market_cap, lm.stock_pe, lm.price_to_book, lm.dividend_yield,
               lm.book_value, lm.roce, lm.roe, lm.enterprise_value, lm.ebitda_ttm,
               lm.ev_ebitda, lm.ev_sales, lm.net_debt, lm.fcf_yield, lm.peg,
               lm.metrics_date
        FROM base b
        LEFT JOIN latest_metrics lm ON lm.stock_id = b.stock_id
        LEFT JOIN latest_price lp ON lp.stock_id = b.stock_id
        ORDER BY b.trading_symbol
        """
    )
    if frame.empty:
        return pd.DataFrame(columns=list(SNAPSHOT_COLUMNS))
    for column in SNAPSHOT_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[list(SNAPSHOT_COLUMNS)]
    if require_metrics:
        frame = frame[frame["metrics_date"].notna()].reset_index(drop=True)
    return frame


def stock_screen(
    search: str = "",
    exchange: str = "All",
    sector: str = "All",
    industry: str = "All",
    require_metrics: bool = False,
    sort_by: str = "market_cap",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated identity filter over the stored metrics snapshot."""
    sort_column = STOCK_SCREEN_SORT_COLUMNS.get(sort_by)
    if not sort_column:
        raise ValueError(f"invalid sort_by: {sort_by}")
    direction = "desc" if str(sort_dir).lower() == "desc" else "asc"
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    frame = build_stock_metrics_snapshot(require_metrics=require_metrics)
    metrics_available = int(frame["metrics_date"].notna().sum()) if not frame.empty else 0

    if frame.empty:
        return {
            "rows": [],
            "total": 0,
            "limit": limit,
            "offset": offset,
            "snapshot_size": 0,
            "metrics_available": 0,
            "columns": list(SNAPSHOT_COLUMNS),
        }

    mask = pd.Series(True, index=frame.index)
    needle = (search or "").strip()
    if needle:
        upper = needle.upper()
        mask &= (
            frame["trading_symbol"].astype(str).str.upper().str.contains(upper, regex=False)
            | frame["company_name"].fillna("").astype(str).str.upper().str.contains(upper, regex=False)
        )
    if exchange and exchange != "All":
        mask &= frame["exchange"].astype(str) == exchange
    if sector and sector != "All":
        mask &= frame["sector_name"].fillna("").astype(str) == sector
    if industry and industry != "All":
        mask &= frame["industry_name"].fillna("").astype(str) == industry

    filtered = frame.loc[mask].copy()
    ascending = direction == "asc"
    filtered = filtered.sort_values(
        by=sort_column,
        ascending=ascending,
        na_position="last",
        kind="mergesort",
    )
    total = int(len(filtered))
    page = filtered.iloc[offset : offset + limit]
    rows = _records_json_safe(page)
    return {
        "rows": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "snapshot_size": int(len(frame)),
        "metrics_available": metrics_available,
        "columns": list(SNAPSHOT_COLUMNS),
    }


def snapshot_records_for_plugins(*, require_metrics: bool = True) -> list[dict[str, Any]]:
    frame = build_stock_metrics_snapshot(require_metrics=require_metrics)
    return _records_json_safe(frame)
