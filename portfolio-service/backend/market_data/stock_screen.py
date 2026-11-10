"""Stock screener snapshot + identity filters over stored metrics only."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

from backend.reference_service import _query

# Columns plugins and the results grid may use. Keep screens/README.md in sync.
SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "trading_symbol",
    "company_name",
    "exchange",
    "sector_name",
    "industry_name",
    "market_cap_class",
    "price_close",
    "sma_200",
    "market_cap",
    "market_cap_cr",
    "stock_pe",
    "price_to_book",
    "dividend_yield",
    "book_value",
    "roce",
    "roe",
    "roa",
    "enterprise_value",
    "ebitda_ttm",
    "ev_ebitda",
    "ev_sales",
    "net_debt",
    "fcf_yield",
    "peg",
    "earnings_yield",
    "debt_to_equity",
    "interest_coverage",
    "operating_margin",
    "asset_turnover",
    "profit_growth_3y",
    "sales_growth_3y",
    "promoter_holding",
    "pledged_pct",
    "cfo",
    "net_profit",
    "current_ratio",
    "dividend_payout",
    "metrics_date",
)

STOCK_SCREEN_SORT_COLUMNS = {
    "trading_symbol": "trading_symbol",
    "company_name": "company_name",
    "sector_name": "sector_name",
    "industry_name": "industry_name",
    "market_cap": "market_cap",
    "market_cap_cr": "market_cap_cr",
    "stock_pe": "stock_pe",
    "price_to_book": "price_to_book",
    "dividend_yield": "dividend_yield",
    "roe": "roe",
    "roce": "roce",
    "roa": "roa",
    "ev_ebitda": "ev_ebitda",
    "price_close": "price_close",
    "profit_growth_3y": "profit_growth_3y",
    "sales_growth_3y": "sales_growth_3y",
    "debt_to_equity": "debt_to_equity",
}


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


def _pct_to_fraction(series: pd.Series) -> pd.Series:
    """Convert percent-point fundamentals (15 or 63) to fractions; leave fractions alone."""
    values = pd.to_numeric(series, errors="coerce")
    return values.where(values.isna() | (values.abs() <= 1.5), values / 100.0)


def build_stock_metrics_snapshot(*, require_metrics: bool = False) -> pd.DataFrame:
    """Latest identity + daily metrics + fundamentals/shareholding/SMA overlays."""
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
        ),
        sma_200 AS (
          SELECT stock_id, AVG(px) AS sma_200
          FROM (
            SELECT p.stock_id,
                   COALESCE(p.adj_close, p.close) AS px,
                   ROW_NUMBER() OVER (PARTITION BY p.stock_id ORDER BY p.trading_date DESC) AS rn
            FROM market_data.stock_daily_prices p
            JOIN base b ON b.stock_id = p.stock_id
            WHERE COALESCE(p.adj_close, p.close) IS NOT NULL
          ) ranked
          WHERE rn <= 200
          GROUP BY stock_id
          HAVING COUNT(*) >= 150
        ),
        latest_share AS (
          SELECT DISTINCT ON (h.stock_id)
                 h.stock_id, h.promoter_pct
          FROM market_data.stock_shareholding_history h
          JOIN base b ON b.stock_id = h.stock_id
          ORDER BY h.stock_id, h.period_end_date DESC
        ),
        annual_fund AS (
          SELECT v.stock_id, r.metric_code, v.metric_value, v.period_end_date,
                 ROW_NUMBER() OVER (
                   PARTITION BY v.stock_id, r.metric_code
                   ORDER BY v.period_end_date DESC
                 ) AS rn
          FROM market_data.stock_fundamental_values v
          JOIN market_data.fundamental_metric_reference r ON r.metric_id = v.metric_id
          JOIN base b ON b.stock_id = v.stock_id
          WHERE v.reporting_period = 'ANNUAL'
            AND v.reporting_basis = 'CONSOLIDATED'
            AND r.metric_code = ANY (ARRAY[
              'DEBT_TO_EQUITY','INTEREST_COVERAGE','OPERATING_MARGIN','ROE','ROCE',
              'NET_PROFIT','REVENUE','SALES','CASH_FROM_OPERATING_ACTIVITIES',
              'OPERATING_CASH_FLOW','TOTAL_ASSETS','PAT_MARGIN','REVENUE_GROWTH','EPS_GROWTH'
            ])
        ),
        latest_fund AS (
          SELECT stock_id,
                 MAX(metric_value) FILTER (WHERE metric_code = 'DEBT_TO_EQUITY' AND rn = 1) AS debt_to_equity,
                 MAX(metric_value) FILTER (WHERE metric_code = 'INTEREST_COVERAGE' AND rn = 1) AS interest_coverage,
                 MAX(metric_value) FILTER (WHERE metric_code = 'OPERATING_MARGIN' AND rn = 1) AS operating_margin_raw,
                 MAX(metric_value) FILTER (WHERE metric_code = 'NET_PROFIT' AND rn = 1) AS net_profit,
                 MAX(metric_value) FILTER (WHERE metric_code = 'REVENUE' AND rn = 1) AS revenue,
                 MAX(metric_value) FILTER (WHERE metric_code = 'SALES' AND rn = 1) AS sales,
                 MAX(metric_value) FILTER (WHERE metric_code = 'CASH_FROM_OPERATING_ACTIVITIES' AND rn = 1) AS cfo_cfa,
                 MAX(metric_value) FILTER (WHERE metric_code = 'OPERATING_CASH_FLOW' AND rn = 1) AS cfo_ocf,
                 MAX(metric_value) FILTER (WHERE metric_code = 'TOTAL_ASSETS' AND rn = 1) AS total_assets,
                 MAX(metric_value) FILTER (WHERE metric_code = 'NET_PROFIT' AND rn = 1) AS np_latest,
                 MAX(metric_value) FILTER (WHERE metric_code = 'NET_PROFIT' AND rn = 4) AS np_older,
                 MAX(metric_value) FILTER (WHERE metric_code = 'REVENUE' AND rn = 1) AS rev_latest,
                 MAX(metric_value) FILTER (WHERE metric_code = 'REVENUE' AND rn = 4) AS rev_older,
                 MAX(metric_value) FILTER (WHERE metric_code = 'SALES' AND rn = 1) AS sales_latest,
                 MAX(metric_value) FILTER (WHERE metric_code = 'SALES' AND rn = 4) AS sales_older
          FROM annual_fund
          GROUP BY stock_id
        )
        SELECT b.trading_symbol, b.company_name, b.exchange, b.sector_name, b.industry_name,
               b.market_cap_class, lp.price_close, sma.sma_200,
               lm.market_cap,
               CASE WHEN lm.market_cap IS NULL THEN NULL ELSE lm.market_cap / 10000000.0 END AS market_cap_cr,
               lm.stock_pe, lm.price_to_book, lm.dividend_yield,
               lm.book_value, lm.roce, lm.roe, lm.enterprise_value, lm.ebitda_ttm,
               lm.ev_ebitda, lm.ev_sales, lm.net_debt, lm.fcf_yield, lm.peg,
               CASE WHEN lm.stock_pe IS NULL OR lm.stock_pe <= 0 THEN NULL ELSE 1.0 / lm.stock_pe END AS earnings_yield,
               lf.debt_to_equity, lf.interest_coverage, lf.operating_margin_raw AS operating_margin,
               lf.net_profit,
               COALESCE(lf.cfo_cfa, lf.cfo_ocf) AS cfo,
               lf.total_assets,
               lf.np_latest, lf.np_older, lf.rev_latest, lf.rev_older, lf.sales_latest, lf.sales_older,
               CASE WHEN sh.promoter_pct IS NULL THEN NULL ELSE sh.promoter_pct / 100.0 END AS promoter_holding,
               CAST(NULL AS numeric) AS pledged_pct,
               CAST(NULL AS numeric) AS current_ratio,
               CAST(NULL AS numeric) AS dividend_payout,
               lm.metrics_date
        FROM base b
        LEFT JOIN latest_metrics lm ON lm.stock_id = b.stock_id
        LEFT JOIN latest_price lp ON lp.stock_id = b.stock_id
        LEFT JOIN sma_200 sma ON sma.stock_id = b.stock_id
        LEFT JOIN latest_share sh ON sh.stock_id = b.stock_id
        LEFT JOIN latest_fund lf ON lf.stock_id = b.stock_id
        ORDER BY b.trading_symbol
        """
    )
    if frame.empty:
        return pd.DataFrame(columns=list(SNAPSHOT_COLUMNS))

    # Normalize percent-point fundamentals to fractions for plugins.
    if "operating_margin" in frame.columns:
        frame["operating_margin"] = _pct_to_fraction(frame["operating_margin"])

    # Derived growth (3y CAGR) when four annual points exist.
    def _cagr(latest: Any, older: Any) -> float | None:
        try:
            a = float(latest)
            b = float(older)
        except (TypeError, ValueError):
            return None
        if a <= 0 or b <= 0:
            return None
        return float((a / b) ** (1.0 / 3.0) - 1.0)

    profit_growth = []
    sales_growth = []
    roa = []
    asset_turnover = []
    for _, row in frame.iterrows():
        profit_growth.append(_cagr(row.get("np_latest"), row.get("np_older")))
        sales_growth.append(
            _cagr(row.get("rev_latest"), row.get("rev_older"))
            if row.get("rev_latest") is not None and row.get("rev_older") is not None
            else _cagr(row.get("sales_latest"), row.get("sales_older"))
        )
        try:
            np_ = float(row["net_profit"]) if row.get("net_profit") is not None else None
            assets = float(row["total_assets"]) if row.get("total_assets") is not None else None
            rev = row.get("rev_latest")
            if rev is None:
                rev = row.get("sales_latest")
            rev_f = float(rev) if rev is not None else None
        except (TypeError, ValueError):
            np_, assets, rev_f = None, None, None
        if np_ is not None and assets not in (None, 0):
            roa.append(np_ / assets)
        else:
            roa.append(None)
        if rev_f is not None and assets not in (None, 0):
            asset_turnover.append(rev_f / assets)
        else:
            asset_turnover.append(None)

    frame["profit_growth_3y"] = profit_growth
    frame["sales_growth_3y"] = sales_growth
    frame["roa"] = roa
    frame["asset_turnover"] = asset_turnover

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
