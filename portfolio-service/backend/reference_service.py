"""Read-only access to Supabase market_data reference tables."""
import os
import re
import uuid
from datetime import date

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values, register_uuid
from dotenv import load_dotenv
from .market_data.index_history import quote_identifier, resolve_index_history_columns
from .market_data.mutual_fund_analytics import METRIC_PERIODS, metric_period_rank_sql

load_dotenv()
register_uuid()

SCREEN_SORT_COLUMNS = {
    "scheme_name": "scheme_name",
    "trailing_return": "trailing_return",
    "cagr": "cagr",
    "sharpe": "sharpe",
    "maximum_drawdown": "maximum_drawdown",
    "aum": "aum",
    "expense_ratio": "expense_ratio",
}


def _query(sql: str, params=()) -> pd.DataFrame:
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [item[0] for item in cursor.description]
            frame = pd.DataFrame(cursor.fetchall(), columns=columns)
            return frame.astype(object).where(pd.notnull(frame), None)


def mutual_funds(search: str = "", amc: str = "All", category: str = "All", subcategory: str = "All", plan_type: str = "All", option_type: str = "All") -> pd.DataFrame:
    return _query("""
        SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name,
               s.subcategory_name, m.plan_type, m.option_type
        FROM market_data.mutual_fund_reference m
        JOIN market_data.amc_reference a ON a.amc_id = m.amc_id
        JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id = m.subcategory_id
        JOIN market_data.mutual_fund_categories c ON c.category_id = s.category_id
        WHERE (%s = '' OR m.scheme_name ILIKE %s OR m.scheme_code ILIKE %s)
          AND (%s = 'All' OR a.amc_name = %s) AND (%s = 'All' OR c.category_name = %s)
          AND (%s = 'All' OR s.subcategory_name = %s) AND (%s = 'All' OR m.plan_type = %s) AND (%s = 'All' OR m.option_type = %s)
        ORDER BY m.scheme_name
    """, (search, f"%{search}%", f"%{search}%", amc, amc, category, category, subcategory, subcategory, plan_type, plan_type, option_type, option_type))


def stock_categories() -> list[str]:
    return _query("SELECT DISTINCT sector_name FROM market_data.sector_reference ORDER BY sector_name")["sector_name"].tolist()

def filter_values(kind: str) -> list[str]:
    queries = {"exchange": "SELECT DISTINCT exchange AS value FROM market_data.stock_reference ORDER BY value", "industry": "SELECT DISTINCT industry_name AS value FROM market_data.industry_reference ORDER BY value", "amc": "SELECT DISTINCT amc_name AS value FROM market_data.amc_reference ORDER BY value", "category": "SELECT DISTINCT category_name AS value FROM market_data.mutual_fund_categories ORDER BY value", "subcategory": "SELECT DISTINCT subcategory_name AS value FROM market_data.mutual_fund_subcategories ORDER BY value"}
    if kind not in queries: return []
    return _query(queries[kind])["value"].tolist()


def stocks(search: str = "", exchange: str = "All", sector: str = "All", industry: str = "All") -> pd.DataFrame:
    return _query("""
        SELECT s.trading_symbol, s.company_name, s.exchange,
               sr.sector_name, ir.industry_name, s.is_active
        FROM market_data.stock_reference s
        LEFT JOIN market_data.sector_reference sr ON sr.sector_id = s.sector_id
        LEFT JOIN market_data.industry_reference ir ON ir.industry_id = s.industry_id
        WHERE (%s = '' OR s.trading_symbol ILIKE %s OR s.company_name ILIKE %s)
          AND (%s = 'All' OR s.exchange = %s) AND (%s = 'All' OR sr.sector_name = %s) AND (%s = 'All' OR ir.industry_name = %s)
        ORDER BY s.trading_symbol
    """, (search, f"%{search}%", f"%{search}%", exchange, exchange, sector, sector, industry, industry))


_METRIC_SELECT = """m.metric_date AS date, m.market_cap, m.stock_pe, m.price_to_book,
    m.dividend_yield, m.book_value, m.roce, m.roe, m.calculation_method,
    m.enterprise_value, m.ebitda_ttm, m.ev_ebitda, m.ev_sales, m.net_debt,
    m.fcf_yield, m.peg"""


def stock_detail(symbol: str):
    frame = _query(
        """SELECT s.stock_id, s.trading_symbol, s.company_name, s.exchange,
                  s.isin, s.bse_code, s.listing_date, s.listing_status, s.market_cap_class,
                  sr.sector_name, ir.industry_name, s.is_active
           FROM market_data.stock_reference s
           LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id
           LEFT JOIN market_data.industry_reference ir ON ir.industry_id=s.industry_id
           WHERE s.trading_symbol=%s""",
        (symbol,),
    )
    return None if frame.empty else frame.iloc[0].to_dict()


CURATED_FUNDAMENTAL_GROUPS = {
    "profit_and_loss": ["REVENUE", "SALES", "OPERATING_PROFIT", "OPERATING_MARGIN", "EBITDA", "NET_PROFIT", "EPS"],
    "balance_sheet": ["EQUITY_CAPITAL", "RESERVES", "BORROWINGS", "TOTAL_DEBT", "NET_DEBT", "TOTAL_ASSETS"],
    "cash_flow": ["CASH_FROM_OPERATING_ACTIVITIES", "OPERATING_CASH_FLOW", "FREE_CASH_FLOW", "NET_CASH_FLOW"],
    "profitability": ["ROE", "ROCE", "PAT_MARGIN"],
    "growth": ["REVENUE_GROWTH", "EPS_GROWTH"],
    "leverage": ["DEBT_TO_EQUITY", "INTEREST_COVERAGE"],
}

FUNDAMENTAL_DEFINITIONS = {
    "REVENUE": "Top-line sales for the reporting period",
    "SALES": "Reported sales (alias of revenue when present)",
    "OPERATING_PROFIT": "Profit from core operations",
    "OPERATING_MARGIN": "Operating profit as % of revenue",
    "EBITDA": "Earnings before interest, tax, depreciation and amortisation",
    "NET_PROFIT": "Profit after tax",
    "EPS": "Earnings per share",
    "ROE": "Net profit / average equity",
    "ROCE": "EBIT / capital employed",
    "PAT_MARGIN": "Net profit as % of revenue",
    "REVENUE_GROWTH": "Period-over-period revenue growth",
    "EPS_GROWTH": "Period-over-period EPS growth",
    "DEBT_TO_EQUITY": "Total debt / equity",
    "INTEREST_COVERAGE": "EBIT / interest expense",
    "FREE_CASH_FLOW": "Cash from operations minus capex (when disclosed)",
    "NET_DEBT": "Interest-bearing debt minus cash",
}


def stock_detail_enriched(symbol: str, last_sync_by_kind: dict | None = None):
    """Identity plus latest price, daily metrics, and freshness in one round-trip."""
    frame = _query(
        f"""
        WITH base AS (
          SELECT s.stock_id, s.trading_symbol, s.company_name, s.exchange,
                 s.isin, s.bse_code, s.listing_date, s.listing_status, s.market_cap_class,
                 s.business_summary,
                 sr.sector_name, ir.industry_name, s.is_active
          FROM market_data.stock_reference s
          LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id
          LEFT JOIN market_data.industry_reference ir ON ir.industry_id=s.industry_id
          WHERE s.trading_symbol=%s
        ),
        latest_price AS (
          SELECT p.trading_date AS date,
                 COALESCE(p.adj_close, p.close) AS close,
                 p.close AS raw_close, p.adj_close, p.volume
          FROM market_data.stock_daily_prices p
          JOIN base b ON b.stock_id=p.stock_id
          ORDER BY p.trading_date DESC LIMIT 1
        ),
        latest_metrics AS (
          SELECT {_METRIC_SELECT}
          FROM market_data.stock_daily_metrics m
          JOIN base b ON b.stock_id=m.stock_id
          ORDER BY m.metric_date DESC LIMIT 1
        ),
        price_range AS (
          SELECT MAX(p.high) AS high_52w, MIN(p.low) AS low_52w
          FROM market_data.stock_daily_prices p
          JOIN base b ON b.stock_id=p.stock_id
          JOIN latest_price lp ON TRUE
          WHERE p.trading_date >= (lp.date - INTERVAL '365 days')
            AND p.high IS NOT NULL
            AND p.low IS NOT NULL
        ),
        freshness AS (
          SELECT
            (SELECT MAX(v.period_end_date) FROM market_data.stock_fundamental_values v
             JOIN base b ON b.stock_id=v.stock_id) AS latest_fundamental_period_end,
            (SELECT MAX(h.period_end_date) FROM market_data.stock_shareholding_history h
             JOIN base b ON b.stock_id=h.stock_id) AS latest_shareholding_period_end,
            (SELECT MAX(p.trading_date) FROM market_data.stock_daily_prices p
             JOIN base b ON b.stock_id=p.stock_id) AS latest_technical_calculated_at
        )
        SELECT b.*,
               lp.date AS price_date, lp.close AS price_close, lp.raw_close, lp.adj_close AS price_adj_close,
               lp.volume AS price_volume, pr.high_52w, pr.low_52w,
               lm.date AS metrics_date, lm.market_cap, lm.stock_pe, lm.price_to_book, lm.dividend_yield,
               lm.book_value, lm.roce, lm.roe, lm.calculation_method,
               lm.enterprise_value, lm.ebitda_ttm, lm.ev_ebitda, lm.ev_sales, lm.net_debt,
               lm.fcf_yield, lm.peg,
               f.latest_fundamental_period_end, f.latest_shareholding_period_end,
               f.latest_technical_calculated_at
        FROM base b
        LEFT JOIN latest_price lp ON TRUE
        LEFT JOIN latest_metrics lm ON TRUE
        LEFT JOIN freshness f ON TRUE
        LEFT JOIN price_range pr ON TRUE
        """,
        (symbol,),
    )
    if frame.empty:
        return None
    row = frame.iloc[0].to_dict()
    latest_price = None
    if row.get("price_date") is not None:
        adj_close = row.pop("price_adj_close", None)
        latest_price = {
            "date": row.pop("price_date"),
            "close": row.pop("price_close"),
            "raw_close": row.pop("raw_close", None),
            "adj_close": adj_close,
            "volume": row.pop("price_volume", None),
            "high_52w": row.pop("high_52w", None),
            "low_52w": row.pop("low_52w", None),
            "adjusted": adj_close is not None,
        }
    else:
        for key in ("price_date", "price_close", "raw_close", "price_adj_close", "price_volume", "high_52w", "low_52w"):
            row.pop(key, None)

    metric_keys = [
        "metrics_date", "market_cap", "stock_pe", "price_to_book", "dividend_yield", "book_value",
        "roce", "roe", "calculation_method", "enterprise_value", "ebitda_ttm", "ev_ebitda",
        "ev_sales", "net_debt", "fcf_yield", "peg",
    ]
    latest_metrics = None
    if row.get("metrics_date") is not None:
        latest_metrics = {"date": row["metrics_date"]}
        for key in metric_keys:
            if key == "metrics_date":
                continue
            latest_metrics[key] = row.get(key)
        latest_metrics["as_of"] = row["metrics_date"]
        latest_metrics["source"] = "yfinance"
    for key in metric_keys:
        row.pop(key, None)

    summary = row.get("business_summary")
    if summary is not None and not isinstance(summary, str):
        row["business_summary"] = None
    latest_fund = row.pop("latest_fundamental_period_end", None)
    latest_share = row.pop("latest_shareholding_period_end", None)
    latest_tech = row.pop("latest_technical_calculated_at", None)
    row.pop("stock_id", None)

    return {
        **row,
        "latest_price": latest_price,
        "latest_daily_metrics": latest_metrics,
        "corporate_actions_available": False,
        "adjusted_history_available": bool(latest_price and latest_price.get("adj_close") is not None),
        "data_sources": {
            "prices": "yfinance",
            "daily_metrics": "yfinance",
            "fundamentals": "screener",
            "technicals": "derived",
            "master": "seed",
        },
        "freshness": {
            "latest_price_date": None if latest_price is None else latest_price.get("date"),
            "latest_fundamental_period_end": latest_fund,
            "latest_shareholding_period_end": latest_share,
            "latest_technical_calculated_at": latest_tech,
            "last_sync_by_kind": last_sync_by_kind or {},
        },
    }


def stock_valuation(symbol: str) -> dict | None:
    """Trailing valuation snapshot with as_of and source; nulls when inputs missing."""
    detail = stock_detail_enriched(symbol)
    if detail is None:
        return None
    metrics = detail.get("latest_daily_metrics") or {}
    return {
        "trading_symbol": symbol,
        "company_name": detail.get("company_name"),
        "as_of": metrics.get("as_of") or metrics.get("date"),
        "source": metrics.get("source") or "yfinance",
        "forward_estimates_available": False,
        "metrics": {
            "market_cap": metrics.get("market_cap"),
            "enterprise_value": metrics.get("enterprise_value"),
            "stock_pe": metrics.get("stock_pe"),
            "price_to_book": metrics.get("price_to_book"),
            "ev_ebitda": metrics.get("ev_ebitda"),
            "ev_sales": metrics.get("ev_sales"),
            "dividend_yield": metrics.get("dividend_yield"),
            "fcf_yield": metrics.get("fcf_yield"),
            "peg": metrics.get("peg"),
            "ebitda_ttm": metrics.get("ebitda_ttm"),
            "net_debt": metrics.get("net_debt"),
            "book_value": metrics.get("book_value"),
            "roe": metrics.get("roe"),
            "roce": metrics.get("roce"),
        },
        "notes": [
            "Trailing multiples only; forward PE is unavailable without a licensed estimate source.",
            "Corporate-action-adjusted valuation inputs remain unavailable until a licensed CA feed is configured.",
        ],
    }


def stock_peers(symbol: str, by: str = "sector", limit: int = 8) -> dict | None:
    detail = stock_detail(symbol)
    if detail is None:
        return None
    by = (by or "sector").lower()
    if by not in {"sector", "industry"}:
        by = "sector"
    limit = max(1, min(int(limit or 8), 20))
    group = detail.get("sector_name") if by == "sector" else detail.get("industry_name")
    if not group:
        return {"symbol": symbol, "by": by, "group": None, "peers": []}

    group_filter = "sr.sector_name=%s" if by == "sector" else "ir.industry_name=%s"
    frame = _query(
        f"""
        WITH peers AS (
          SELECT s.stock_id, s.trading_symbol, s.company_name
          FROM market_data.stock_reference s
          LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id
          LEFT JOIN market_data.industry_reference ir ON ir.industry_id=s.industry_id
          WHERE {group_filter} AND s.trading_symbol <> %s
          ORDER BY s.trading_symbol
          LIMIT %s
        ),
        latest_price AS (
          SELECT DISTINCT ON (p.stock_id) p.stock_id, COALESCE(p.adj_close, p.close) AS close
          FROM market_data.stock_daily_prices p
          JOIN peers pe ON pe.stock_id=p.stock_id
          ORDER BY p.stock_id, p.trading_date DESC
        ),
        latest_metrics AS (
          SELECT DISTINCT ON (m.stock_id) m.stock_id, m.market_cap, m.stock_pe, m.price_to_book, m.roe, m.roce,
                 m.ev_ebitda, m.enterprise_value
          FROM market_data.stock_daily_metrics m
          JOIN peers pe ON pe.stock_id=m.stock_id
          ORDER BY m.stock_id, m.metric_date DESC
        )
        SELECT pe.trading_symbol, pe.company_name, lp.close AS latest_close,
               lm.market_cap, lm.stock_pe, lm.price_to_book, lm.roe, lm.roce,
               lm.ev_ebitda, lm.enterprise_value
        FROM peers pe
        LEFT JOIN latest_price lp ON lp.stock_id=pe.stock_id
        LEFT JOIN latest_metrics lm ON lm.stock_id=pe.stock_id
        ORDER BY pe.trading_symbol
        """,
        (group, symbol, limit),
    )
    peers = []
    for _, row in frame.iterrows():
        metrics = {
            "market_cap": row["market_cap"],
            "stock_pe": row["stock_pe"],
            "price_to_book": row["price_to_book"],
            "roe": row["roe"],
            "roce": row["roce"],
            "ev_ebitda": row["ev_ebitda"],
            "enterprise_value": row["enterprise_value"],
        }
        if all(v is None for v in metrics.values()):
            metrics = None
        peers.append({
            "trading_symbol": row["trading_symbol"],
            "company_name": row["company_name"],
            "latest_close": row["latest_close"],
            "latest_metrics": metrics,
        })
    return {"symbol": symbol, "by": by, "group": group, "peers": peers}


def stock_compare(symbols: list[str]) -> list[dict]:
    cleaned = [s.strip().upper() for s in symbols if s and s.strip()]
    if not cleaned:
        return []
    frame = _query(
        """
        WITH wanted AS (
          SELECT s.stock_id, s.trading_symbol, s.company_name, sr.sector_name
          FROM market_data.stock_reference s
          LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id
          WHERE s.trading_symbol = ANY(%s)
        ),
        latest_price AS (
          SELECT DISTINCT ON (p.stock_id) p.stock_id, p.trading_date AS date,
                 COALESCE(p.adj_close, p.close) AS close
          FROM market_data.stock_daily_prices p
          JOIN wanted w ON w.stock_id=p.stock_id
          ORDER BY p.stock_id, p.trading_date DESC
        ),
        latest_metrics AS (
          SELECT DISTINCT ON (m.stock_id) m.stock_id, m.metric_date AS date, m.market_cap,
                 m.stock_pe, m.price_to_book, m.dividend_yield, m.roe, m.roce,
                 m.enterprise_value, m.ev_ebitda, m.fcf_yield, m.peg
          FROM market_data.stock_daily_metrics m
          JOIN wanted w ON w.stock_id=m.stock_id
          ORDER BY m.stock_id, m.metric_date DESC
        )
        SELECT w.trading_symbol, w.company_name, w.sector_name,
               lp.close AS latest_close, lp.date AS latest_price_date,
               lm.date AS metrics_date, lm.market_cap, lm.stock_pe, lm.price_to_book,
               lm.dividend_yield, lm.roe, lm.roce, lm.enterprise_value, lm.ev_ebitda,
               lm.fcf_yield, lm.peg
        FROM wanted w
        LEFT JOIN latest_price lp ON lp.stock_id=w.stock_id
        LEFT JOIN latest_metrics lm ON lm.stock_id=w.stock_id
        """,
        (cleaned,),
    )
    by_symbol = {row["trading_symbol"]: row for _, row in frame.iterrows()}
    rows = []
    for symbol in cleaned:
        row = by_symbol.get(symbol)
        if row is None:
            continue
        metrics = None
        if row.get("metrics_date") is not None:
            metrics = {
                "date": row["metrics_date"],
                "market_cap": row["market_cap"],
                "stock_pe": row["stock_pe"],
                "price_to_book": row["price_to_book"],
                "dividend_yield": row["dividend_yield"],
                "roe": row["roe"],
                "roce": row["roce"],
                "enterprise_value": row["enterprise_value"],
                "ev_ebitda": row["ev_ebitda"],
                "fcf_yield": row["fcf_yield"],
                "peg": row["peg"],
            }
        rows.append({
            "trading_symbol": symbol,
            "company_name": row.get("company_name"),
            "sector_name": row.get("sector_name"),
            "latest_close": row.get("latest_close"),
            "latest_price_date": row.get("latest_price_date"),
            "latest_metrics": metrics,
        })
    return rows


def stock_fundamentals_summary(symbol: str, reporting_period: str = "ANNUAL", reporting_basis: str = "CONSOLIDATED") -> dict | None:
    if stock_detail(symbol) is None:
        return None
    reporting_period = reporting_period or "ANNUAL"
    reporting_basis = reporting_basis or "CONSOLIDATED"
    curated_codes = [code for codes in CURATED_FUNDAMENTAL_GROUPS.values() for code in codes]
    frame = stock_fundamentals(symbol, reporting_period, reporting_basis, "", "")
    if not frame.empty:
        frame = frame[frame["metric_code"].isin(curated_codes)]
    periods = sorted({str(p) for p in frame["period_end_date"].tolist()}, reverse=True) if not frame.empty else []
    groups: dict[str, dict] = {name: {code: {} for code in codes} for name, codes in CURATED_FUNDAMENTAL_GROUPS.items()}
    if not frame.empty:
        for _, row in frame.iterrows():
            code = row["metric_code"]
            period = str(row["period_end_date"])
            for group_name, codes in CURATED_FUNDAMENTAL_GROUPS.items():
                if code in codes:
                    groups[group_name][code][period] = row["metric_value"]
                    break
    return {
        "reporting_period": reporting_period,
        "reporting_basis": reporting_basis,
        "periods": periods,
        "groups": groups,
        "definitions": {code: FUNDAMENTAL_DEFINITIONS[code] for code in curated_codes if code in FUNDAMENTAL_DEFINITIONS},
        "source": "screener",
        "note": "Standalone and consolidated values are never mixed in one view.",
    }


def mutual_fund_detail(scheme_code: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_code=%s""", (scheme_code,))
    return None if frame.empty else frame.iloc[0].to_dict()

def mutual_fund_detail_by_name(name: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_name=%s""", (name,))
    return None if frame.empty else frame.iloc[0].to_dict()


def _fund_name_key(name: str) -> str:
    text = name.lower()
    for compact, spaced in (
        ("smallcap", "small cap"),
        ("flexicap", "flexi cap"),
        ("midcap", "mid cap"),
        ("multicap", "multi cap"),
        ("largemidcap", "large mid cap"),
    ):
        text = text.replace(compact, spaced)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _holding_name_core(name: str) -> str:
    text = _fund_name_key(name)
    for word in ("direct", "plan", "growth", "option", "bonus", "idcw", "dividend"):
        text = re.sub(rf"\b{word}\b", " ", text)
    return " ".join(text.split())


def _is_direct_growth(plan: str, option: str, scheme_name: str) -> bool:
    blob = f"{plan} {option} {scheme_name}".lower()
    if any(word in blob for word in ("bonus", "idcw", "dividend")):
        return False
    return "direct" in blob and "growth" in blob


def match_scheme_code(holding_name: str, funds: list[tuple]) -> str | None:
    """Return a scheme code only when one direct-growth scheme contains the holding name."""
    core = _holding_name_core(holding_name)
    if not core:
        return None
    hits = []
    for fund in funds:
        code, scheme_name = fund[0], fund[1]
        plan = fund[2] if len(fund) > 2 else ""
        option = fund[3] if len(fund) > 3 else ""
        if core in _fund_name_key(str(scheme_name)) and _is_direct_growth(str(plan or ""), str(option or ""), str(scheme_name)):
            hits.append(str(code))
    if len(hits) == 1:
        return hits[0]
    return None


def match_mutual_fund_codes(names: list[str]) -> dict[str, str]:
    wanted = [name for name in dict.fromkeys(names) if name]
    if not wanted:
        return {}
    frame = _query(
        """SELECT scheme_code, scheme_name, COALESCE(plan_type, ''), COALESCE(option_type, '')
           FROM market_data.mutual_fund_reference"""
    )
    funds = [] if frame.empty else list(frame.itertuples(index=False, name=None))
    matched = {}
    for name in wanted:
        code = match_scheme_code(name, funds)
        if code:
            matched[name] = code
    return matched


def mutual_fund_detail_enriched(scheme_code: str, last_sync_by_kind: dict | None = None):
    """Identity plus latest NAV, metrics, enrichment, benchmark, and freshness."""
    base = mutual_fund_detail(scheme_code)
    if base is None:
        return None

    nav_frame = _query(
        """SELECT h.nav_date AS date, h.nav
           FROM market_data.mutual_fund_nav_history h
           JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id
           WHERE m.scheme_code=%s ORDER BY h.nav_date DESC LIMIT 1""",
        (scheme_code,),
    )
    metrics_frame = _query(
        f"""SELECT x.as_of_date, x.metric_period, x.current_nav, x.trailing_return, x.cagr,
                  x.standard_deviation, x.sharpe, x.sortino, x.maximum_drawdown, x.alpha, x.beta,
                  x.observations, x.aligned_observations, x.risk_free_rate, x.calculation_version,
                  x.benchmark_as_of_date, x.available, x.reason
           FROM market_data.mutual_fund_metric_snapshots x
           JOIN market_data.mutual_fund_reference m ON m.scheme_id=x.scheme_id
           WHERE m.scheme_code=%s
           ORDER BY x.available DESC, x.as_of_date DESC, {metric_period_rank_sql("x.metric_period")}
           LIMIT 1""",
        (scheme_code,),
    )
    enrichment_frame = _query(
        """SELECT e.as_of_date, e.aum, e.expense_ratio, e.exit_load, e.fund_manager,
                  e.fund_house, e.scheme_category, e.scheme_start_date, e.provider_status
           FROM market_data.mutual_fund_enrichment e
           JOIN market_data.mutual_fund_reference m ON m.scheme_id=e.scheme_id
           WHERE m.scheme_code=%s ORDER BY e.as_of_date DESC LIMIT 1""",
        (scheme_code,),
    )
    bench = mutual_fund_benchmark(scheme_code)
    bench_payload = {"available": False, "reason": "No benchmark is mapped"}
    latest_bench_date = None
    if bench and bench.get("index_code"):
        bench_payload = {
            "available": True,
            "index_code": bench.get("index_code"),
            "index_name": bench.get("index_name"),
            "index_id": bench.get("index_id"),
        }
        latest_bench = _index_history_query(
            lambda d, c, _volume_expr=None: f"""SELECT h.{quote_identifier(d)} AS date
                FROM market_data.index_daily_history h
                JOIN market_data.mutual_fund_reference m ON m.benchmark_index_id=h.index_id
                WHERE m.scheme_code=%s ORDER BY h.{quote_identifier(d)} DESC LIMIT 1""",
            (scheme_code,),
        )
        if not latest_bench.empty:
            latest_bench_date = latest_bench.iloc[0].get("date")

    latest_nav = None if nav_frame.empty else nav_frame.iloc[0].to_dict()
    latest_metrics = None if metrics_frame.empty else metrics_frame.iloc[0].to_dict()
    latest_enrichment = None if enrichment_frame.empty else enrichment_frame.iloc[0].to_dict()

    return {
        **base,
        "latest_nav": latest_nav,
        "latest_metrics": latest_metrics,
        "latest_enrichment": latest_enrichment,
        "benchmark": bench_payload,
        "freshness": {
            "latest_nav_date": None if latest_nav is None else latest_nav.get("date"),
            "latest_metrics_as_of": None if latest_metrics is None else latest_metrics.get("as_of_date"),
            "latest_enrichment_as_of": None if latest_enrichment is None else latest_enrichment.get("as_of_date"),
            "latest_benchmark_history_date": latest_bench_date,
            "last_sync_by_kind": last_sync_by_kind or {},
        },
    }


def mutual_fund_similar(scheme_code: str) -> pd.DataFrame:
    return _query("""SELECT m2.scheme_code,m2.scheme_name,a.amc_name,c.category_name,s.subcategory_name,m2.plan_type,m2.option_type
      FROM market_data.mutual_fund_reference m1 JOIN market_data.mutual_fund_reference m2 ON m2.subcategory_id=m1.subcategory_id
      JOIN market_data.amc_reference a ON a.amc_id=m2.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m2.subcategory_id
      JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m1.scheme_code=%s AND m2.scheme_code<>%s AND m2.is_active=TRUE ORDER BY m2.scheme_name LIMIT 20""", (scheme_code,scheme_code))


def mutual_fund_similar_enriched(scheme_code: str) -> list[dict]:
    """Peers in the same subcategory, plan, and option, on the source scheme's period."""
    if mutual_fund_detail(scheme_code) is None:
        return []
    period_rank = metric_period_rank_sql("x.metric_period")
    frame = _query(
        f"""WITH source AS (
              SELECT scheme_id, scheme_code, subcategory_id, plan_type, option_type
              FROM market_data.mutual_fund_reference
              WHERE scheme_code=%s
            ),
            source_period AS (
              SELECT x.metric_period
              FROM market_data.mutual_fund_metric_snapshots x
              JOIN source s ON s.scheme_id=x.scheme_id
              ORDER BY x.available DESC, x.as_of_date DESC, {period_rank}
              LIMIT 1
            ),
            peers AS (
              SELECT m2.scheme_id, m2.scheme_code, m2.scheme_name, a.amc_name,
                     c.category_name, s.subcategory_name, m2.plan_type, m2.option_type
              FROM source src
              JOIN market_data.mutual_fund_reference m2
                ON m2.subcategory_id=src.subcategory_id
               AND m2.scheme_code<>src.scheme_code
               AND m2.is_active=TRUE
               AND m2.plan_type IS NOT DISTINCT FROM src.plan_type
               AND m2.option_type IS NOT DISTINCT FROM src.option_type
              JOIN market_data.amc_reference a ON a.amc_id=m2.amc_id
              JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m2.subcategory_id
              JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id
              ORDER BY m2.scheme_name
              LIMIT 20
            ),
            latest_metrics AS (
              SELECT DISTINCT ON (x.scheme_id)
                     x.scheme_id, x.current_nav, x.cagr, x.trailing_return, x.sharpe
              FROM market_data.mutual_fund_metric_snapshots x
              JOIN peers p ON p.scheme_id=x.scheme_id
              WHERE x.metric_period = (SELECT metric_period FROM source_period)
              ORDER BY x.scheme_id, x.available DESC, x.as_of_date DESC
            ),
            latest_nav AS (
              SELECT DISTINCT ON (h.scheme_id)
                     h.scheme_id, h.nav AS latest_nav
              FROM market_data.mutual_fund_nav_history h
              JOIN peers p ON p.scheme_id=h.scheme_id
              ORDER BY h.scheme_id, h.nav_date DESC
            )
            SELECT p.scheme_code, p.scheme_name, p.amc_name, p.category_name, p.subcategory_name,
                   p.plan_type, p.option_type,
                   (SELECT metric_period FROM source_period) AS metric_period,
                   COALESCE(lm.current_nav, ln.latest_nav) AS latest_nav,
                   lm.cagr, lm.trailing_return, lm.sharpe
            FROM peers p
            LEFT JOIN latest_metrics lm ON lm.scheme_id=p.scheme_id
            LEFT JOIN latest_nav ln ON ln.scheme_id=p.scheme_id
            ORDER BY p.scheme_name""",
        (scheme_code,),
    )
    return frame.to_dict(orient="records")


def mutual_fund_screen(
    search: str = "",
    amc: str = "All",
    category: str = "All",
    subcategory: str = "All",
    plan_type: str = "All",
    option_type: str = "All",
    metric_period: str = "1Y",
    min_trailing: float | None = None,
    min_cagr: float | None = None,
    min_sharpe: float | None = None,
    max_drawdown: float | None = None,
    min_aum: float | None = None,
    max_aum: float | None = None,
    max_expense_ratio: float | None = None,
    require_metrics: bool = False,
    sort_by: str = "scheme_name",
    sort_dir: str = "asc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Batch screener over identity + latest enrichment + latest metric snapshot."""
    if metric_period not in METRIC_PERIODS:
        raise ValueError(f"invalid metric_period: {metric_period}")
    sort_column = SCREEN_SORT_COLUMNS.get(sort_by)
    if not sort_column:
        raise ValueError(f"invalid sort_by: {sort_by}")
    direction = "DESC" if str(sort_dir).lower() == "desc" else "ASC"
    # Numeric sorts put nulls last so ranked results stay useful.
    nulls = "NULLS LAST" if sort_column != "scheme_name" else ""
    order_sql = f"{sort_column} {direction} {nulls}".strip()
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    frame = _query(
        f"""WITH schemes AS (
              SELECT m.scheme_id, m.scheme_code, m.scheme_name, a.amc_name,
                     c.category_name, s.subcategory_name, m.plan_type, m.option_type
              FROM market_data.mutual_fund_reference m
              JOIN market_data.amc_reference a ON a.amc_id=m.amc_id
              JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id
              JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id
              WHERE m.is_active=TRUE
                AND (%s = '' OR m.scheme_code ILIKE %s OR m.scheme_name ILIKE %s)
                AND (%s = 'All' OR a.amc_name = %s)
                AND (%s = 'All' OR c.category_name = %s)
                AND (%s = 'All' OR s.subcategory_name = %s)
                AND (%s = 'All' OR m.plan_type = %s)
                AND (%s = 'All' OR m.option_type = %s)
            ),
            latest_metrics AS (
              SELECT DISTINCT ON (x.scheme_id)
                     x.scheme_id, x.as_of_date, x.trailing_return, x.cagr, x.sharpe,
                     x.maximum_drawdown, x.current_nav, x.available
              FROM market_data.mutual_fund_metric_snapshots x
              JOIN schemes p ON p.scheme_id=x.scheme_id
              WHERE x.metric_period=%s
              ORDER BY x.scheme_id, x.available DESC, x.as_of_date DESC
            ),
            latest_enrichment AS (
              SELECT DISTINCT ON (e.scheme_id)
                     e.scheme_id, e.aum, e.expense_ratio
              FROM market_data.mutual_fund_enrichment e
              JOIN schemes p ON p.scheme_id=e.scheme_id
              ORDER BY e.scheme_id, e.as_of_date DESC
            ),
            latest_nav AS (
              SELECT DISTINCT ON (h.scheme_id)
                     h.scheme_id, h.nav AS latest_nav
              FROM market_data.mutual_fund_nav_history h
              JOIN schemes p ON p.scheme_id=h.scheme_id
              ORDER BY h.scheme_id, h.nav_date DESC
            ),
            joined AS (
              SELECT p.scheme_code, p.scheme_name, p.amc_name, p.category_name, p.subcategory_name,
                     p.plan_type, p.option_type,
                     COALESCE(lm.current_nav, ln.latest_nav) AS latest_nav,
                     lm.trailing_return, lm.cagr, lm.sharpe, lm.maximum_drawdown,
                     le.aum, le.expense_ratio,
                     COALESCE(lm.available, FALSE) AS metrics_available,
                     lm.as_of_date AS metrics_as_of
              FROM schemes p
              LEFT JOIN latest_metrics lm ON lm.scheme_id=p.scheme_id
              LEFT JOIN latest_enrichment le ON le.scheme_id=p.scheme_id
              LEFT JOIN latest_nav ln ON ln.scheme_id=p.scheme_id
            )
            SELECT *, COUNT(*) OVER() AS total_count
            FROM joined
            WHERE (%s IS FALSE OR metrics_available IS TRUE)
              AND (%s IS NULL OR trailing_return >= %s)
              AND (%s IS NULL OR cagr >= %s)
              AND (%s IS NULL OR sharpe >= %s)
              AND (%s IS NULL OR maximum_drawdown >= %s)
              AND (%s IS NULL OR aum >= %s)
              AND (%s IS NULL OR aum <= %s)
              AND (%s IS NULL OR expense_ratio <= %s)
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s""",
        (
            search, f"%{search}%", f"%{search}%",
            amc, amc, category, category, subcategory, subcategory, plan_type, plan_type, option_type, option_type,
            metric_period,
            require_metrics,
            min_trailing, min_trailing,
            min_cagr, min_cagr,
            min_sharpe, min_sharpe,
            max_drawdown, max_drawdown,
            min_aum, min_aum,
            max_aum, max_aum,
            max_expense_ratio, max_expense_ratio,
            limit, offset,
        ),
    )
    total = 0 if frame.empty else int(frame.iloc[0]["total_count"] or 0)
    rows = []
    if not frame.empty:
        for row in frame.to_dict(orient="records"):
            row.pop("total_count", None)
            rows.append(row)
    return {"metric_period": metric_period, "total": total, "limit": limit, "offset": offset, "rows": rows}


def mutual_fund_compare(scheme_codes: list[str], metric_period: str = "1Y") -> list[dict]:
    """Batch compare funds for one metric period."""
    if metric_period not in METRIC_PERIODS:
        raise ValueError(f"invalid metric_period: {metric_period}")
    codes = [str(code).strip() for code in scheme_codes if str(code).strip()]
    if not codes:
        return []
    if len(codes) > 10:
        raise ValueError("compare at most 10 schemes")
    frame = _query(
        """WITH schemes AS (
              SELECT m.scheme_id, m.scheme_code, m.scheme_name, a.amc_name, c.category_name,
                     s.subcategory_name, m.plan_type, m.option_type, m.benchmark_index_id
              FROM market_data.mutual_fund_reference m
              JOIN market_data.amc_reference a ON a.amc_id=m.amc_id
              JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id
              JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id
              WHERE m.scheme_code = ANY(%s)
            ),
            latest_metrics AS (
              SELECT DISTINCT ON (x.scheme_id)
                     x.scheme_id, x.as_of_date, x.trailing_return, x.cagr, x.standard_deviation,
                     x.sharpe, x.sortino, x.maximum_drawdown, x.alpha, x.beta, x.available, x.reason,
                     x.risk_free_rate, x.calculation_version, x.current_nav
              FROM market_data.mutual_fund_metric_snapshots x
              JOIN schemes p ON p.scheme_id=x.scheme_id
              WHERE x.metric_period=%s
              ORDER BY x.scheme_id, x.available DESC, x.as_of_date DESC
            ),
            latest_enrichment AS (
              SELECT DISTINCT ON (e.scheme_id)
                     e.scheme_id, e.aum, e.expense_ratio, e.exit_load, e.fund_manager
              FROM market_data.mutual_fund_enrichment e
              JOIN schemes p ON p.scheme_id=e.scheme_id
              ORDER BY e.scheme_id, e.as_of_date DESC
            ),
            latest_nav AS (
              SELECT DISTINCT ON (h.scheme_id)
                     h.scheme_id, h.nav_date AS date, h.nav
              FROM market_data.mutual_fund_nav_history h
              JOIN schemes p ON p.scheme_id=h.scheme_id
              ORDER BY h.scheme_id, h.nav_date DESC
            )
            SELECT p.scheme_code, p.scheme_name, p.amc_name, p.category_name, p.subcategory_name,
                   p.plan_type, p.option_type,
                   ln.date AS nav_date, COALESCE(lm.current_nav, ln.nav) AS nav,
                   lm.as_of_date, lm.trailing_return, lm.cagr, lm.standard_deviation, lm.sharpe,
                   lm.sortino, lm.maximum_drawdown, lm.alpha, lm.beta, lm.available, lm.reason,
                   lm.risk_free_rate, lm.calculation_version,
                   le.aum, le.expense_ratio, le.exit_load, le.fund_manager,
                   i.index_code, i.index_name
            FROM schemes p
            LEFT JOIN latest_metrics lm ON lm.scheme_id=p.scheme_id
            LEFT JOIN latest_enrichment le ON le.scheme_id=p.scheme_id
            LEFT JOIN latest_nav ln ON ln.scheme_id=p.scheme_id
            LEFT JOIN market_data.index_reference i ON i.index_id=p.benchmark_index_id""",
        (codes, metric_period),
    )
    by_code = {row["scheme_code"]: row for row in frame.to_dict(orient="records")}
    rows = []
    for code in codes:
        item = by_code.get(code)
        if item is None:
            continue
        bench_code = item.get("index_code")
        rows.append({
            "scheme_code": item.get("scheme_code"),
            "scheme_name": item.get("scheme_name"),
            "amc_name": item.get("amc_name"),
            "category_name": item.get("category_name"),
            "subcategory_name": item.get("subcategory_name"),
            "plan_type": item.get("plan_type"),
            "option_type": item.get("option_type"),
            "latest_nav": None if item.get("nav") is None else {"date": item.get("nav_date"), "nav": item.get("nav")},
            "metric_period": metric_period,
            "metrics": {
                "as_of_date": item.get("as_of_date"),
                "trailing_return": item.get("trailing_return"),
                "cagr": item.get("cagr"),
                "standard_deviation": item.get("standard_deviation"),
                "sharpe": item.get("sharpe"),
                "sortino": item.get("sortino"),
                "maximum_drawdown": item.get("maximum_drawdown"),
                "alpha": item.get("alpha"),
                "beta": item.get("beta"),
                "available": item.get("available"),
                "reason": item.get("reason"),
                "risk_free_rate": item.get("risk_free_rate"),
                "calculation_version": item.get("calculation_version"),
            },
            "enrichment": {
                "aum": item.get("aum"),
                "expense_ratio": item.get("expense_ratio"),
                "exit_load": item.get("exit_load"),
                "fund_manager": item.get("fund_manager"),
            },
            "benchmark": (
                {"available": True, "index_code": bench_code, "index_name": item.get("index_name")}
                if bench_code
                else {"available": False, "reason": "No benchmark is mapped"}
            ),
        })
    return rows


def stock_history(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query(
        """SELECT p.trading_date AS date, p.open, p.high, p.low,
                  COALESCE(p.adj_close, p.close) AS close, p.close AS raw_close,
                  p.adj_close, p.volume,
                  (p.adj_close IS NOT NULL) AS is_adjusted
           FROM market_data.stock_daily_prices p
           JOIN market_data.stock_reference s ON s.stock_id=p.stock_id
           WHERE s.trading_symbol=%s
             AND (%s IS NULL OR p.trading_date >= %s)
             AND (%s IS NULL OR p.trading_date <= %s)
           ORDER BY p.trading_date""",
        (symbol, from_date, from_date, to_date, to_date),
    )

def mutual_fund_history(scheme_code: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("SELECT h.nav_date AS date,h.nav FROM market_data.mutual_fund_nav_history h JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id WHERE m.scheme_code=%s AND (%s IS NULL OR h.nav_date >= %s) AND (%s IS NULL OR h.nav_date <= %s) ORDER BY h.nav_date", (scheme_code, from_date, from_date, to_date, to_date))

def mutual_fund_metric_snapshots(scheme_code: str) -> list[dict]:
    frame = _query(
        f"""SELECT x.as_of_date,x.metric_period,x.current_nav,x.trailing_return,x.cagr,
        x.rolling_latest,x.rolling_min,x.rolling_max,x.rolling_median,
        x.standard_deviation,x.sharpe,x.sortino,x.maximum_drawdown,x.alpha,x.beta,
        x.observations,x.aligned_observations,x.available,x.reason,x.calculation_version
        FROM market_data.mutual_fund_metric_snapshots x
        JOIN market_data.mutual_fund_reference m ON m.scheme_id=x.scheme_id
        WHERE m.scheme_code=%s
        ORDER BY x.as_of_date DESC, {metric_period_rank_sql("x.metric_period")}""",
        (scheme_code,),
    )
    return frame.to_dict(orient="records")

def mutual_fund_enrichment(scheme_code: str) -> list[dict]:
    frame = _query("""SELECT e.as_of_date,e.aum,e.expense_ratio,e.exit_load,e.yield_to_maturity,
        e.yield_to_maturity_unit,e.fund_manager,e.rating,e.fund_house,e.scheme_type,
        e.scheme_category,e.scheme_start_date,e.provider_status,e.warnings
        FROM market_data.mutual_fund_enrichment e
        JOIN market_data.mutual_fund_reference m ON m.scheme_id=e.scheme_id
        WHERE m.scheme_code=%s ORDER BY e.as_of_date DESC""", (scheme_code,))
    if not frame.empty:
        return frame.to_dict(orient="records")
    # Reference metadata is still useful when optional enrichment has not been
    # fetched yet, so the fund-facts panel never appears blank.
    fallback = _query("""SELECT m.scheme_code,m.scheme_name,a.amc_name AS fund_house,
        c.category_name AS scheme_category,s.subcategory_name,
        m.plan_type,m.option_type,'REFERENCE' AS provider_status
        FROM market_data.mutual_fund_reference m
        JOIN market_data.amc_reference a ON a.amc_id=m.amc_id
        JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id
        JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id
        WHERE m.scheme_code=%s""", (scheme_code,))
    return fallback.to_dict(orient="records")

def mutual_fund_benchmark(scheme_code: str):
    frame = _query("""SELECT i.index_id,i.index_code,i.index_name,m.benchmark_index_id
        FROM market_data.mutual_fund_reference m
        LEFT JOIN market_data.index_reference i ON i.index_id=m.benchmark_index_id
        WHERE m.scheme_code=%s""", (scheme_code,))
    return None if frame.empty else frame.iloc[0].to_dict()


def _disclosure_holdings(disclosure_id) -> list[dict]:
    frame = _query(
        """SELECT security_name, isin, sector, market_cap_bucket, instrument_type, weight_pct
           FROM market_data.mutual_fund_portfolio_holdings
           WHERE disclosure_id=%s ORDER BY weight_pct DESC, security_name""",
        (disclosure_id,),
    )
    return frame.to_dict(orient="records")


def _latest_disclosures(scheme_code: str, limit: int = 2) -> list[dict]:
    frame = _query(
        """SELECT d.disclosure_id, d.as_of_date, d.source_name, d.equity_pct, d.debt_pct,
                  d.cash_pct, d.other_pct, d.warnings
           FROM market_data.mutual_fund_portfolio_disclosures d
           JOIN market_data.mutual_fund_reference m ON m.scheme_id=d.scheme_id
           WHERE m.scheme_code=%s
           ORDER BY d.as_of_date DESC
           LIMIT %s""",
        (scheme_code, limit),
    )
    return frame.to_dict(orient="records")


def mutual_fund_holdings_snapshot(scheme_code: str, top_n: int = 20) -> dict:
    """Latest disclosure with allocations, concentration, and MoM holding changes."""
    from .market_data.mutual_fund_holdings import concentration_stats, holding_changes

    if mutual_fund_detail(scheme_code) is None:
        return None
    disclosures = _latest_disclosures(scheme_code, limit=2)
    if not disclosures:
        return {
            "available": False,
            "reason": "No portfolio disclosure synced yet",
            "scheme_code": scheme_code,
        }
    current = disclosures[0]
    previous = disclosures[1] if len(disclosures) > 1 else None
    holdings = _disclosure_holdings(current["disclosure_id"])
    prior_holdings = _disclosure_holdings(previous["disclosure_id"]) if previous else None
    top_n = max(1, min(int(top_n), 50))
    sector_alloc: dict[str, float] = {}
    mcap_alloc: dict[str, float] = {}
    for row in holdings:
        sector = row.get("sector") or "Unknown"
        mcap = row.get("market_cap_bucket") or "Unknown"
        weight = float(row["weight_pct"])
        sector_alloc[sector] = sector_alloc.get(sector, 0.0) + weight
        mcap_alloc[mcap] = mcap_alloc.get(mcap, 0.0) + weight
    stale = False
    as_of = current.get("as_of_date")
    if as_of is not None:
        try:
            from datetime import date, datetime, timedelta

            as_date = as_of if hasattr(as_of, "year") else date.fromisoformat(str(as_of)[:10])
            stale = as_date < (date.today() - timedelta(days=120))
        except Exception:
            stale = False
    return {
        "available": True,
        "scheme_code": scheme_code,
        "as_of_date": current.get("as_of_date"),
        "source_name": current.get("source_name"),
        "stale": stale,
        "asset_allocation": {
            "equity_pct": current.get("equity_pct"),
            "debt_pct": current.get("debt_pct"),
            "cash_pct": current.get("cash_pct"),
            "other_pct": current.get("other_pct"),
        },
        "sector_allocation": [
            {"sector": key, "weight_pct": value}
            for key, value in sorted(sector_alloc.items(), key=lambda item: item[1], reverse=True)
        ],
        "market_cap_allocation": [
            {"market_cap_bucket": key, "weight_pct": value}
            for key, value in sorted(mcap_alloc.items(), key=lambda item: item[1], reverse=True)
        ],
        "concentration": concentration_stats([row["weight_pct"] for row in holdings]),
        "top_holdings": holdings[:top_n],
        "changes": holding_changes(holdings, prior_holdings),
        "prior_as_of_date": None if previous is None else previous.get("as_of_date"),
        "warnings": current.get("warnings") or [],
    }


def mutual_fund_overlap(scheme_codes: list[str]) -> dict:
    """Pairwise min-weight overlap for up to 10 schemes with latest disclosures."""
    from .market_data.mutual_fund_holdings import min_weight_overlap, sector_overlap

    codes = [code.strip() for code in scheme_codes if code and code.strip()][:10]
    if len(codes) < 2:
        raise ValueError("overlap requires at least 2 scheme_codes")
    snapshots = []
    for code in codes:
        detail = mutual_fund_detail(code)
        if detail is None:
            continue
        disclosures = _latest_disclosures(code, limit=1)
        if not disclosures:
            snapshots.append(
                {
                    "scheme_code": code,
                    "scheme_name": detail.get("scheme_name"),
                    "available": False,
                    "reason": "No portfolio disclosure",
                    "as_of_date": None,
                    "holdings": [],
                    "stale": True,
                }
            )
            continue
        holdings = _disclosure_holdings(disclosures[0]["disclosure_id"])
        snap = mutual_fund_holdings_snapshot(code, top_n=50)
        snapshots.append(
            {
                "scheme_code": code,
                "scheme_name": detail.get("scheme_name"),
                "available": True,
                "as_of_date": disclosures[0].get("as_of_date"),
                "stale": bool(snap and snap.get("stale")),
                "holdings": holdings,
            }
        )
    pairs = []
    for i in range(len(snapshots)):
        for j in range(i + 1, len(snapshots)):
            left, right = snapshots[i], snapshots[j]
            if not left["available"] or not right["available"]:
                pairs.append(
                    {
                        "scheme_a": left["scheme_code"],
                        "scheme_b": right["scheme_code"],
                        "available": False,
                        "reason": "Missing disclosure on one or both schemes",
                    }
                )
                continue
            overlap = min_weight_overlap(left["holdings"], right["holdings"])
            pairs.append(
                {
                    "scheme_a": left["scheme_code"],
                    "scheme_b": right["scheme_code"],
                    "available": True,
                    "as_of_a": left["as_of_date"],
                    "as_of_b": right["as_of_date"],
                    "stale_warning": left["stale"] or right["stale"],
                    **overlap,
                    "sector_overlap": sector_overlap(left["holdings"], right["holdings"]),
                }
            )
    return {
        "method": "sum_of_min_weights",
        "schemes": [
            {
                "scheme_code": item["scheme_code"],
                "scheme_name": item.get("scheme_name"),
                "available": item["available"],
                "as_of_date": item.get("as_of_date"),
                "stale": item.get("stale"),
                "reason": item.get("reason"),
            }
            for item in snapshots
        ],
        "pairs": pairs,
    }


def mutual_fund_managers(scheme_code: str) -> dict:
    """Manager assignment history with tenure-adjusted scheme returns."""
    from .market_data.mutual_fund_holdings import parse_date, tenure_return_from_nav

    detail = mutual_fund_detail(scheme_code)
    if detail is None:
        return None
    frame = _query(
        """SELECT a.manager_name, a.start_date, a.end_date, a.is_current, a.source_name
           FROM market_data.mutual_fund_manager_assignments a
           JOIN market_data.mutual_fund_reference m ON m.scheme_id=a.scheme_id
           WHERE m.scheme_code=%s
           ORDER BY a.is_current DESC, a.start_date DESC""",
        (scheme_code,),
    )
    nav = mutual_fund_history(scheme_code)
    assignments = []
    for row in frame.to_dict(orient="records"):
        start = parse_date(row.get("start_date"))
        end = parse_date(row.get("end_date"))
        tenure = None
        if start is not None:
            tenure = tenure_return_from_nav(nav, start, end)
        assignments.append(
            {
                **row,
                "tenure_absolute_return": tenure,
                "note": "Tenure return uses scheme NAV only over the assignment window — not full scheme history.",
            }
        )
    return {
        "scheme_code": scheme_code,
        "scheme_name": detail.get("scheme_name"),
        "available": bool(assignments),
        "reason": None if assignments else "No manager assignments synced yet",
        "assignments": assignments,
    }

def mutual_fund_benchmark_history(scheme_code: str) -> list[dict]:
    return _index_history_query(
        lambda d, c, volume_expr: f'''SELECT h.{quote_identifier(d)} AS date,h.open,h.high,h.low,h.{quote_identifier(c)} AS close,{volume_expr}
        FROM market_data.index_daily_history h
        JOIN market_data.mutual_fund_reference m ON m.benchmark_index_id=h.index_id
        WHERE m.scheme_code=%s ORDER BY h.{quote_identifier(d)}''',
        (scheme_code,),
    ).to_dict(orient="records")

def benchmark_list() -> list[dict]:
    return _query("SELECT index_id,index_code,index_name FROM market_data.index_reference ORDER BY index_name").to_dict(orient="records")

def benchmark_history(index_code: str) -> list[dict]:
    return _index_history_query(
        lambda d, c, volume_expr: f'''SELECT h.{quote_identifier(d)} AS date,h.open,h.high,h.low,h.{quote_identifier(c)} AS close,{volume_expr}
        FROM market_data.index_daily_history h JOIN market_data.index_reference i ON i.index_id=h.index_id
        WHERE i.index_code=%s ORDER BY h.{quote_identifier(d)}''',
        (index_code,),
    ).to_dict(orient="records")


def benchmark_snapshot(codes: list[str]) -> list[dict]:
    """Last two closes per index. Unknown codes are omitted."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for code in codes:
        text = (code or "").strip()
        if not text or text.upper() in seen:
            continue
        seen.add(text.upper())
        cleaned.append(text)
    if not cleaned:
        return []
    frame = _index_history_query(
        lambda d, c, _volume: f'''
        WITH ranked AS (
          SELECT i.index_code, i.index_name,
                 h.{quote_identifier(d)} AS as_of,
                 h.{quote_identifier(c)} AS close,
                 ROW_NUMBER() OVER (
                   PARTITION BY i.index_code ORDER BY h.{quote_identifier(d)} DESC
                 ) AS rn
          FROM market_data.index_daily_history h
          JOIN market_data.index_reference i ON i.index_id=h.index_id
          WHERE upper(i.index_code) = ANY(%s)
        )
        SELECT index_code, index_name,
               MAX(close) FILTER (WHERE rn = 1) AS close,
               MAX(close) FILTER (WHERE rn = 2) AS previous_close,
               MAX(as_of) FILTER (WHERE rn = 1) AS as_of
        FROM ranked
        WHERE rn <= 2
        GROUP BY index_code, index_name
        ''',
        ([code.upper() for code in cleaned],),
    )
    by_code = {} if frame.empty else {str(row["index_code"]).upper(): row for _, row in frame.iterrows()}
    rows = []
    for code in cleaned:
        row = by_code.get(code.upper())
        if row is None:
            continue
        close = row.get("close")
        previous = row.get("previous_close")
        change = None
        if close is not None and previous is not None and float(previous) != 0:
            change = (float(close) - float(previous)) / float(previous) * 100
        rows.append({
            "index_code": row.get("index_code"),
            "index_name": row.get("index_name"),
            "close": close,
            "previous_close": previous,
            "change_pct": change,
            "as_of": row.get("as_of"),
        })
    return rows


def _index_history_query(sql_builder, params=()) -> pd.DataFrame:
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            date_column, close_column = resolve_index_history_columns(cursor)
            cursor.execute(
                """SELECT 1 FROM information_schema.columns
                   WHERE table_schema='market_data' AND table_name='index_daily_history'
                     AND column_name='volume' LIMIT 1"""
            )
            volume_expr = "h.volume" if cursor.fetchone() else "NULL::bigint AS volume"
            cursor.execute(sql_builder(date_column, close_column, volume_expr), params)
            columns = [item[0] for item in cursor.description]
            frame = pd.DataFrame(cursor.fetchall(), columns=columns)
            return frame.astype(object).where(pd.notnull(frame), None)

def stock_daily_metrics(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query(
        f"""SELECT {_METRIC_SELECT}
        FROM market_data.stock_daily_metrics m
        JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
        WHERE s.trading_symbol=%s AND (%s IS NULL OR m.metric_date >= %s)
          AND (%s IS NULL OR m.metric_date <= %s) ORDER BY m.metric_date""",
        (symbol, from_date, from_date, to_date, to_date),
    )

def stock_fundamentals(symbol: str, reporting_period: str = "", reporting_basis: str = "", metric_code: str = "", statement_type: str = "") -> pd.DataFrame:
    from backend.market_data.providers.screener import canonical_statement_type
    frame = _query("""SELECT v.period_end_date, v.period_start_date, v.reporting_period,
        v.reporting_basis, r.metric_code, r.metric_name, r.statement_type, r.unit,
        v.metric_value, v.publication_date, v.version, v.source_id
        FROM market_data.stock_fundamental_values v
        JOIN market_data.stock_reference s ON s.stock_id=v.stock_id
        JOIN market_data.fundamental_metric_reference r ON r.metric_id=v.metric_id
        WHERE s.trading_symbol=%s AND (%s='' OR v.reporting_period=%s)
          AND (%s='' OR v.reporting_basis=%s) AND (%s='' OR r.metric_code=%s)
        ORDER BY v.period_end_date DESC, r.metric_code""",
        (symbol, reporting_period, reporting_period, reporting_basis, reporting_basis, metric_code, metric_code))
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["statement_type"] = [
        canonical_statement_type(code, stored)
        for code, stored in zip(frame["metric_code"], frame["statement_type"])
    ]
    if statement_type:
        frame = frame[frame["statement_type"] == statement_type]
    return frame

def stock_shareholding(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("""SELECT h.period_end_date, h.promoter_pct, h.fii_pct, h.dii_pct,
        h.government_pct, h.public_pct, h.shareholder_count
        FROM market_data.stock_shareholding_history h
        JOIN market_data.stock_reference s ON s.stock_id=h.stock_id
        WHERE s.trading_symbol=%s AND (%s IS NULL OR h.period_end_date >= %s)
          AND (%s IS NULL OR h.period_end_date <= %s) ORDER BY h.period_end_date""",
        (symbol, from_date, from_date, to_date, to_date))

_TECHNICAL_COLUMNS = [
    "date",
    "indicator_code",
    "indicator_period",
    "parameters",
    "component",
    "indicator_value",
    "calculation_status",
    "calculated_at",
]


def _empty_technicals() -> pd.DataFrame:
    return pd.DataFrame(columns=_TECHNICAL_COLUMNS)


def _load_stored_technicals(symbol: str, indicator: str = "") -> tuple[pd.DataFrame, date | None]:
    """Return (rows, snapshot_trading_date) from the latest-day cache table."""
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """SELECT MAX(t.trading_date)
                       FROM market_data.stock_technical_indicators t
                       JOIN market_data.stock_reference s ON s.stock_id = t.stock_id
                       WHERE s.trading_symbol=%s AND s.is_active=TRUE""",
                    (symbol,),
                )
                snap = cur.fetchone()[0]
                if snap is None:
                    return _empty_technicals(), None
                cur.execute(
                    """SELECT t.trading_date AS date, t.indicator_code, t.indicator_period,
                              t.parameters::text AS parameters, t.component, t.indicator_value,
                              t.calculation_status, t.calculated_at
                       FROM market_data.stock_technical_indicators t
                       JOIN market_data.stock_reference s ON s.stock_id = t.stock_id
                       WHERE s.trading_symbol=%s AND s.is_active=TRUE
                         AND t.trading_date=%s
                         AND (%s = '' OR t.indicator_code = %s)
                       ORDER BY t.indicator_code, t.indicator_period, t.component""",
                    (symbol, snap, indicator.upper() if indicator else "", indicator.upper() if indicator else ""),
                )
                rows = cur.fetchall()
        if not rows:
            return _empty_technicals(), snap
        frame = pd.DataFrame(rows, columns=_TECHNICAL_COLUMNS)
        return frame, snap
    except Exception:
        return _empty_technicals(), None


def _last_ohlc_date(symbol: str) -> date | None:
    try:
        with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """SELECT MAX(p.trading_date)
                       FROM market_data.stock_daily_prices p
                       JOIN market_data.stock_reference s ON s.stock_id = p.stock_id
                       WHERE s.trading_symbol=%s AND s.is_active=TRUE""",
                    (symbol,),
                )
                value = cur.fetchone()[0]
                return value
    except Exception:
        return None


def _technicals_from_ohlc_frame(frame: pd.DataFrame, indicator: str = "") -> pd.DataFrame:
    """Compute latest-day indicators from an OHLC frame (no DB write)."""
    from datetime import datetime, timezone

    from backend.market_data.sync import DEFAULT_INDICATORS, _latest_indicator_rows
    from backend_api.app.technical_indicators import calculate_indicators

    if frame.empty:
        return _empty_technicals()
    try:
        _trading_date, latest_rows = _latest_indicator_rows(frame)
    except RuntimeError:
        calculated = calculate_indicators(frame, DEFAULT_INDICATORS).dropna(subset=["value"])
        if calculated.empty:
            return _empty_technicals()
        latest_rows = calculated
    if indicator:
        latest_rows = latest_rows[latest_rows["indicator_code"] == indicator.upper()]
    if latest_rows.empty:
        return _empty_technicals()
    out = latest_rows.rename(columns={"value": "indicator_value"}).copy()
    out["calculation_status"] = "CURRENT"
    out["calculated_at"] = datetime.now(timezone.utc)
    return out[_TECHNICAL_COLUMNS].reset_index(drop=True)


def stock_technical_indicators(symbol: str, indicator: str = "", from_date=None, to_date=None) -> pd.DataFrame:
    """Return latest-day technicals from Postgres; refresh from OHLC when stale/missing.

    ``from_date`` / ``to_date`` are retained for API compatibility but ignored — only the
    latest trading-day snapshot is stored and returned.
    """
    _ = from_date, to_date
    stored, snap = _load_stored_technicals(symbol, indicator)
    last_ohlc = _last_ohlc_date(symbol)
    if not stored.empty and snap is not None and last_ohlc is not None and snap >= last_ohlc:
        return stored.reset_index(drop=True)

    # Refresh from OHLC only when the price table is reachable; otherwise fall back
    # to an in-memory compute (tests / offline) without hanging on DB writes.
    if last_ohlc is not None:
        try:
            from backend.market_data.sync import sync_technical_indicators

            sync_technical_indicators(symbol)
            stored, _snap = _load_stored_technicals(symbol, indicator)
            if not stored.empty:
                return stored.reset_index(drop=True)
        except Exception:
            pass

    frame = stock_history(symbol, None, None)
    return _technicals_from_ohlc_frame(frame, indicator)

def sync_stock_fundamentals(symbol: str, force: bool = False) -> dict:
    """Fetch Screener consolidated and standalone statements in one job.

    Soft provider failures raise so the sync queue marks the job FAILED instead of
    SUCCEEDED with an empty/failed payload the UI cannot see. One missing basis is a
    warning, not a failure. statement_type is taken from the parsed section and
    corrected on existing reference rows even when force is false.
    """
    from backend.market_data.providers.screener import (
        CONSOLIDATED, STANDALONE, ScreenerParser, build_company_url, fetch_html, metric_statement_types,
    )
    user_agent = "Mozilla/5.0 (compatible; WealthOrbit/1.0)"
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE", (symbol,))
            row = cur.fetchone()
            if not row: raise ValueError(f"Active stock not found: {symbol}")
            stock_id = row[0]
            tagged_types = metric_statement_types()
            if tagged_types:
                cur.execute(
                    """UPDATE market_data.fundamental_metric_reference AS metric
                       SET statement_type = tagged.statement_type, updated_at = NOW()
                       FROM (
                         SELECT * FROM unnest(%s::text[], %s::text[])
                           AS tagged(metric_code, statement_type)
                       ) AS tagged
                       WHERE metric.metric_code = tagged.metric_code
                         AND metric.statement_type <> tagged.statement_type""",
                    (list(tagged_types.keys()), list(tagged_types.values())),
                )
            parsed_by_basis = {}
            basis_warnings = []
            for basis, warning in ((CONSOLIDATED, "consolidated_unavailable"), (STANDALONE, "standalone_unavailable")):
                html = fetch_html(build_company_url(symbol, None, basis), user_agent)
                if not html:
                    basis_warnings.append(warning)
                    continue
                parsed_by_basis[basis] = ScreenerParser(basis).parse(html, stock_id)
            if not parsed_by_basis:
                raise RuntimeError(f"Fundamentals sync failed for {symbol}: screener_html_unavailable")
            if not any(parsed.fundamental_values or parsed.shareholding for parsed in parsed_by_basis.values()):
                raise RuntimeError(f"Fundamentals sync failed for {symbol}: screener_parse_empty")
            # Remove Dec year-ends previously mis-tagged as Oct–Dec quarters.
            cur.execute(
                """DELETE FROM market_data.stock_fundamental_values
                   WHERE stock_id=%s AND reporting_period='QUARTERLY'
                     AND EXTRACT(MONTH FROM period_end_date)=12
                     AND EXTRACT(MONTH FROM period_start_date)=10""",
                (stock_id,),
            )
            if force:
                cur.execute("DELETE FROM market_data.stock_fundamental_values WHERE stock_id=%s", (stock_id,))
                cur.execute("DELETE FROM market_data.stock_shareholding_history WHERE stock_id=%s", (stock_id,))
            from .market_data.sources import ensure_data_source

            source_id = ensure_data_source(cur, "screener")
            counts = {CONSOLIDATED: 0, STANDALONE: 0}
            parser_warnings = 0
            for basis, parsed in parsed_by_basis.items():
                counts[basis] = len(parsed.fundamental_values)
                parser_warnings += len(parsed.warnings)

            # Prefetch metric map once — per-row SELECTs were multi-minute over pgbouncer.
            cur.execute(
                "SELECT metric_code, metric_id, statement_type FROM market_data.fundamental_metric_reference"
            )
            metric_map = {code: (metric_id, statement_type) for code, metric_id, statement_type in cur.fetchall()}
            needed_types = {}
            for parsed in parsed_by_basis.values():
                for value in parsed.fundamental_values:
                    needed_types[value.metric_code] = value.statement_type
            new_metrics = []
            for code, statement_type in needed_types.items():
                existing = metric_map.get(code)
                if existing is None:
                    metric_id = uuid.uuid4()
                    new_metrics.append(
                        (metric_id, code, code.replace("_", " ").title(), statement_type)
                    )
                    metric_map[code] = (metric_id, statement_type)
                elif existing[1] != statement_type:
                    cur.execute(
                        """UPDATE market_data.fundamental_metric_reference
                           SET statement_type=%s, updated_at=NOW()
                           WHERE metric_code=%s""",
                        (statement_type, code),
                    )
                    metric_map[code] = (existing[0], statement_type)
            if new_metrics:
                execute_values(
                    cur,
                    """INSERT INTO market_data.fundamental_metric_reference
                       (metric_id, metric_code, metric_name, statement_type)
                       VALUES %s
                       ON CONFLICT (metric_code) DO NOTHING""",
                    new_metrics,
                    page_size=200,
                )
                # Refresh ids in case ON CONFLICT skipped a concurrent insert.
                cur.execute(
                    "SELECT metric_code, metric_id, statement_type FROM market_data.fundamental_metric_reference"
                )
                metric_map = {
                    code: (metric_id, statement_type)
                    for code, metric_id, statement_type in cur.fetchall()
                }

            fundamental_rows = []
            for parsed in parsed_by_basis.values():
                for value in parsed.fundamental_values:
                    metric = metric_map.get(value.metric_code)
                    if metric is None:
                        continue
                    fundamental_rows.append(
                        (
                            stock_id,
                            metric[0],
                            value.reporting_period,
                            value.period_start,
                            value.period_end,
                            value.reporting_basis,
                            value.value,
                            source_id,
                        )
                    )
            if fundamental_rows:
                execute_values(
                    cur,
                    """INSERT INTO market_data.stock_fundamental_values
                       (stock_id, metric_id, reporting_period, period_start_date, period_end_date,
                        reporting_basis, metric_value, source_id)
                       VALUES %s
                       ON CONFLICT (stock_id, metric_id, reporting_period, reporting_basis, period_end_date)
                       DO UPDATE SET metric_value=EXCLUDED.metric_value,
                                     source_id=EXCLUDED.source_id,
                                     updated_at=NOW()""",
                    fundamental_rows,
                    page_size=500,
                )
                from backend.market_data.fundamentals_retention import prune_fundamental_periods

                prune_fundamental_periods(cur, stock_id)

            shareholding = []
            for basis in (CONSOLIDATED, STANDALONE):
                parsed = parsed_by_basis.get(basis)
                if parsed and parsed.shareholding:
                    shareholding = parsed.shareholding
                    break
            if shareholding:
                execute_values(
                    cur,
                    """INSERT INTO market_data.stock_shareholding_history
                       (stock_id, period_end_date, promoter_pct, fii_pct, dii_pct,
                        government_pct, public_pct, shareholder_count, source_id)
                       VALUES %s
                       ON CONFLICT (stock_id, period_end_date)
                       DO UPDATE SET promoter_pct=EXCLUDED.promoter_pct,
                                     fii_pct=EXCLUDED.fii_pct,
                                     dii_pct=EXCLUDED.dii_pct,
                                     government_pct=EXCLUDED.government_pct,
                                     public_pct=EXCLUDED.public_pct,
                                     shareholder_count=EXCLUDED.shareholder_count,
                                     source_id=EXCLUDED.source_id,
                                     updated_at=NOW()""",
                    [
                        (
                            stock_id,
                            value.period_end,
                            value.promoter_pct,
                            value.fii_pct,
                            value.dii_pct,
                            value.government_pct,
                            value.public_pct,
                            value.shareholder_count,
                            source_id,
                        )
                        for value in shareholding
                    ],
                    page_size=200,
                )
        connection.commit()
    fundamental_rows = counts[CONSOLIDATED] + counts[STANDALONE]
    return {
        "status": "completed",
        "symbol": symbol,
        "fundamental_rows": fundamental_rows,
        "fundamental_rows_consolidated": counts[CONSOLIDATED],
        "fundamental_rows_standalone": counts[STANDALONE],
        "shareholding_rows": len(shareholding),
        "warnings": parser_warnings,
        "basis_warnings": basis_warnings,
        "force": force,
    }
