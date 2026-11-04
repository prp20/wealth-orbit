"""Read-only access to Supabase market_data reference tables."""
import os
import pandas as pd
import psycopg2
from psycopg2.extras import register_uuid
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


def stock_detail(symbol: str):
    frame = _query("SELECT s.trading_symbol, s.company_name, s.exchange, sr.sector_name, ir.industry_name, s.is_active FROM market_data.stock_reference s LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id LEFT JOIN market_data.industry_reference ir ON ir.industry_id=s.industry_id WHERE s.trading_symbol=%s", (symbol,))
    return None if frame.empty else frame.iloc[0].to_dict()


CURATED_FUNDAMENTAL_GROUPS = {
    "profit_and_loss": ["REVENUE", "OPERATING_PROFIT", "OPERATING_MARGIN", "NET_PROFIT", "EPS"],
    "balance_sheet": ["EQUITY_CAPITAL", "RESERVES", "BORROWINGS", "TOTAL_ASSETS"],
    "cash_flow": ["CASH_FROM_OPERATING_ACTIVITIES", "NET_CASH_FLOW"],
}


def stock_detail_enriched(symbol: str, last_sync_by_kind: dict | None = None):
    """Identity plus latest price, daily metrics, and freshness metadata."""
    base = stock_detail(symbol)
    if base is None:
        return None

    price_frame = _query(
        """SELECT p.trading_date AS date, p.close, p.volume
           FROM market_data.stock_daily_prices p
           JOIN market_data.stock_reference s ON s.stock_id=p.stock_id
           WHERE s.trading_symbol=%s ORDER BY p.trading_date DESC LIMIT 1""",
        (symbol,),
    )
    metrics_frame = _query(
        """SELECT m.metric_date AS date, m.market_cap, m.stock_pe, m.price_to_book,
                  m.dividend_yield, m.book_value, m.roce, m.roe, m.calculation_method
           FROM market_data.stock_daily_metrics m
           JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
           WHERE s.trading_symbol=%s ORDER BY m.metric_date DESC LIMIT 1""",
        (symbol,),
    )
    fund_frame = _query(
        """SELECT MAX(v.period_end_date) AS latest_fundamental_period_end
           FROM market_data.stock_fundamental_values v
           JOIN market_data.stock_reference s ON s.stock_id=v.stock_id
           WHERE s.trading_symbol=%s""",
        (symbol,),
    )
    share_frame = _query(
        """SELECT MAX(h.period_end_date) AS latest_shareholding_period_end
           FROM market_data.stock_shareholding_history h
           JOIN market_data.stock_reference s ON s.stock_id=h.stock_id
           WHERE s.trading_symbol=%s""",
        (symbol,),
    )
    tech_frame = _query(
        """SELECT MAX(t.calculated_at) AS latest_technical_calculated_at
           FROM market_data.stock_technical_indicators t
           JOIN market_data.stock_reference s ON s.stock_id=t.stock_id
           WHERE s.trading_symbol=%s""",
        (symbol,),
    )

    latest_price = None if price_frame.empty else price_frame.iloc[0].to_dict()
    latest_metrics = None if metrics_frame.empty else metrics_frame.iloc[0].to_dict()
    latest_fund = None if fund_frame.empty else fund_frame.iloc[0].get("latest_fundamental_period_end")
    latest_share = None if share_frame.empty else share_frame.iloc[0].get("latest_shareholding_period_end")
    latest_tech = None if tech_frame.empty else tech_frame.iloc[0].get("latest_technical_calculated_at")

    return {
        **base,
        "latest_price": latest_price,
        "latest_daily_metrics": latest_metrics,
        "freshness": {
            "latest_price_date": None if latest_price is None else latest_price.get("date"),
            "latest_fundamental_period_end": latest_fund,
            "latest_shareholding_period_end": latest_share,
            "latest_technical_calculated_at": latest_tech,
            "last_sync_by_kind": last_sync_by_kind or {},
        },
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

    if by == "sector":
        peer_frame = stocks(sector=group)
    else:
        peer_frame = stocks(industry=group)
    peer_frame = peer_frame[peer_frame["trading_symbol"] != symbol].head(limit)
    peers = []
    for _, row in peer_frame.iterrows():
        peer_symbol = row["trading_symbol"]
        price = _query(
            """SELECT p.close FROM market_data.stock_daily_prices p
               JOIN market_data.stock_reference s ON s.stock_id=p.stock_id
               WHERE s.trading_symbol=%s ORDER BY p.trading_date DESC LIMIT 1""",
            (peer_symbol,),
        )
        metrics = _query(
            """SELECT m.market_cap, m.stock_pe, m.price_to_book, m.roe, m.roce
               FROM market_data.stock_daily_metrics m
               JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
               WHERE s.trading_symbol=%s ORDER BY m.metric_date DESC LIMIT 1""",
            (peer_symbol,),
        )
        peers.append({
            "trading_symbol": peer_symbol,
            "company_name": row["company_name"],
            "latest_close": None if price.empty else price.iloc[0]["close"],
            "latest_metrics": None if metrics.empty else metrics.iloc[0].to_dict(),
        })
    return {"symbol": symbol, "by": by, "group": group, "peers": peers}


def stock_compare(symbols: list[str]) -> list[dict]:
    rows = []
    for symbol in symbols:
        detail = stock_detail(symbol)
        if detail is None:
            continue
        price = _query(
            """SELECT p.close, p.trading_date AS date FROM market_data.stock_daily_prices p
               JOIN market_data.stock_reference s ON s.stock_id=p.stock_id
               WHERE s.trading_symbol=%s ORDER BY p.trading_date DESC LIMIT 1""",
            (symbol,),
        )
        metrics = _query(
            """SELECT m.metric_date AS date, m.market_cap, m.stock_pe, m.price_to_book,
                      m.dividend_yield, m.roe, m.roce
               FROM market_data.stock_daily_metrics m
               JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
               WHERE s.trading_symbol=%s ORDER BY m.metric_date DESC LIMIT 1""",
            (symbol,),
        )
        rows.append({
            "trading_symbol": symbol,
            "company_name": detail.get("company_name"),
            "sector_name": detail.get("sector_name"),
            "latest_close": None if price.empty else price.iloc[0]["close"],
            "latest_price_date": None if price.empty else price.iloc[0]["date"],
            "latest_metrics": None if metrics.empty else metrics.iloc[0].to_dict(),
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
    }


def mutual_fund_detail(scheme_code: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_code=%s""", (scheme_code,))
    return None if frame.empty else frame.iloc[0].to_dict()

def mutual_fund_detail_by_name(name: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_name=%s""", (name,))
    return None if frame.empty else frame.iloc[0].to_dict()


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
    """Similar funds with latest metric snapshot columns in one batch query."""
    if mutual_fund_detail(scheme_code) is None:
        return []
    period_rank = metric_period_rank_sql("x.metric_period")
    frame = _query(
        f"""WITH peers AS (
              SELECT m2.scheme_id, m2.scheme_code, m2.scheme_name, a.amc_name,
                     c.category_name, s.subcategory_name, m2.plan_type, m2.option_type
              FROM market_data.mutual_fund_reference m1
              JOIN market_data.mutual_fund_reference m2 ON m2.subcategory_id=m1.subcategory_id
              JOIN market_data.amc_reference a ON a.amc_id=m2.amc_id
              JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m2.subcategory_id
              JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id
              WHERE m1.scheme_code=%s AND m2.scheme_code<>%s AND m2.is_active=TRUE
              ORDER BY m2.scheme_name LIMIT 20
            ),
            latest_metrics AS (
              SELECT DISTINCT ON (x.scheme_id)
                     x.scheme_id, x.current_nav, x.cagr, x.trailing_return, x.sharpe
              FROM market_data.mutual_fund_metric_snapshots x
              JOIN peers p ON p.scheme_id=x.scheme_id
              ORDER BY x.scheme_id, x.available DESC, x.as_of_date DESC, {period_rank}
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
                   COALESCE(lm.current_nav, ln.latest_nav) AS latest_nav,
                   lm.cagr, lm.trailing_return, lm.sharpe
            FROM peers p
            LEFT JOIN latest_metrics lm ON lm.scheme_id=p.scheme_id
            LEFT JOIN latest_nav ln ON ln.scheme_id=p.scheme_id
            ORDER BY p.scheme_name""",
        (scheme_code, scheme_code),
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
    return _query("SELECT p.trading_date AS date,p.open,p.high,p.low,p.close,p.volume FROM market_data.stock_daily_prices p JOIN market_data.stock_reference s ON s.stock_id=p.stock_id WHERE s.trading_symbol=%s AND (%s IS NULL OR p.trading_date >= %s) AND (%s IS NULL OR p.trading_date <= %s) ORDER BY p.trading_date", (symbol, from_date, from_date, to_date, to_date))

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
    return _query("""SELECT m.metric_date AS date, m.market_cap, m.stock_pe, m.price_to_book,
        m.dividend_yield, m.book_value, m.roce, m.roe, m.calculation_method
        FROM market_data.stock_daily_metrics m
        JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
        WHERE s.trading_symbol=%s AND (%s IS NULL OR m.metric_date >= %s)
          AND (%s IS NULL OR m.metric_date <= %s) ORDER BY m.metric_date""",
        (symbol, from_date, from_date, to_date, to_date))

def stock_fundamentals(symbol: str, reporting_period: str = "", reporting_basis: str = "", metric_code: str = "", statement_type: str = "") -> pd.DataFrame:
    return _query("""SELECT v.period_end_date, v.period_start_date, v.reporting_period,
        v.reporting_basis, r.metric_code, r.metric_name, r.statement_type, r.unit,
        v.metric_value, v.source_id
        FROM market_data.stock_fundamental_values v
        JOIN market_data.stock_reference s ON s.stock_id=v.stock_id
        JOIN market_data.fundamental_metric_reference r ON r.metric_id=v.metric_id
        WHERE s.trading_symbol=%s AND (%s='' OR v.reporting_period=%s)
          AND (%s='' OR v.reporting_basis=%s) AND (%s='' OR r.metric_code=%s)
          AND (%s='' OR r.statement_type=%s)
        ORDER BY v.period_end_date DESC, r.metric_code""",
        (symbol, reporting_period, reporting_period, reporting_basis, reporting_basis, metric_code, metric_code, statement_type, statement_type))

def stock_shareholding(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("""SELECT h.period_end_date, h.promoter_pct, h.fii_pct, h.dii_pct,
        h.government_pct, h.public_pct, h.shareholder_count
        FROM market_data.stock_shareholding_history h
        JOIN market_data.stock_reference s ON s.stock_id=h.stock_id
        WHERE s.trading_symbol=%s AND (%s IS NULL OR h.period_end_date >= %s)
          AND (%s IS NULL OR h.period_end_date <= %s) ORDER BY h.period_end_date""",
        (symbol, from_date, from_date, to_date, to_date))

def stock_technical_indicators(symbol: str, indicator: str = "", from_date=None, to_date=None) -> pd.DataFrame:
    return _query("""SELECT t.trading_date AS date, t.indicator_code, t.indicator_period,
        t.parameters, t.component, t.indicator_value, t.calculation_status,
        t.calculated_at
        FROM market_data.stock_technical_indicators t
        JOIN market_data.stock_reference s ON s.stock_id=t.stock_id
        WHERE s.trading_symbol=%s AND (%s='' OR t.indicator_code=%s)
          AND (%s IS NULL OR t.trading_date >= %s) AND (%s IS NULL OR t.trading_date <= %s)
        ORDER BY t.trading_date, t.indicator_code, t.component""",
        (symbol, indicator, indicator, from_date, from_date, to_date, to_date))

def sync_stock_fundamentals(symbol: str, force: bool = False) -> dict:
    """Fetch Screener consolidated data and upsert canonical fundamentals.

    Soft provider failures raise so the sync queue marks the job FAILED instead of
    SUCCEEDED with an empty/failed payload the UI cannot see.
    """
    from backend.market_data.providers.screener import ScreenerParser, build_company_url, fetch_html
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE", (symbol,))
            row = cur.fetchone()
            if not row: raise ValueError(f"Active stock not found: {symbol}")
            stock_id = row[0]
            html = fetch_html(build_company_url(symbol, None), "Mozilla/5.0 (compatible; WealthOrbit/1.0)")
            if not html:
                raise RuntimeError(f"Screener returned no HTML for {symbol}")
            parsed = ScreenerParser().parse(html, stock_id)
            if not parsed.fundamental_values and not parsed.shareholding:
                raise RuntimeError(f"Screener parse returned no fundamentals or shareholding for {symbol}")
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
            source_id = None
            cur.execute("SELECT source_id FROM market_data.data_sources WHERE source_name='screener'")
            found = cur.fetchone()
            if found: source_id = found[0]
            else:
                import uuid
                source_id = uuid.uuid4(); cur.execute("INSERT INTO market_data.data_sources(source_id,source_name) VALUES(%s,'screener')", (source_id,))
            metric_ids = {}
            for value in parsed.fundamental_values:
                cur.execute("SELECT metric_id FROM market_data.fundamental_metric_reference WHERE metric_code=%s", (value.metric_code,))
                metric = cur.fetchone()
                if not metric:
                    statement = "PL" if value.metric_code in {"REVENUE","TOTAL_EXPENSES","OPERATING_PROFIT","NET_PROFIT","EPS"} else "BS"
                    import uuid
                    metric_id = uuid.uuid4(); cur.execute("INSERT INTO market_data.fundamental_metric_reference(metric_id,metric_code,metric_name,statement_type) VALUES(%s,%s,%s,%s)", (metric_id,value.metric_code,value.metric_code.replace('_',' ').title(),statement))
                else: metric_id = metric[0]
                metric_ids[value.metric_code] = metric_id
                cur.execute("""INSERT INTO market_data.stock_fundamental_values(stock_id,metric_id,reporting_period,period_start_date,period_end_date,reporting_basis,metric_value,source_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(stock_id,metric_id,reporting_period,reporting_basis,period_end_date)
                    DO UPDATE SET metric_value=EXCLUDED.metric_value,source_id=EXCLUDED.source_id,updated_at=NOW()""", (stock_id,metric_id,value.reporting_period,value.period_start,value.period_end,value.reporting_basis,value.value,source_id))
            for value in parsed.shareholding:
                cur.execute("""INSERT INTO market_data.stock_shareholding_history(stock_id,period_end_date,promoter_pct,fii_pct,dii_pct,government_pct,public_pct,shareholder_count,source_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(stock_id,period_end_date)
                    DO UPDATE SET promoter_pct=EXCLUDED.promoter_pct,fii_pct=EXCLUDED.fii_pct,dii_pct=EXCLUDED.dii_pct,government_pct=EXCLUDED.government_pct,public_pct=EXCLUDED.public_pct,shareholder_count=EXCLUDED.shareholder_count,source_id=EXCLUDED.source_id,updated_at=NOW()""", (stock_id,value.period_end,value.promoter_pct,value.fii_pct,value.dii_pct,value.government_pct,value.public_pct,value.shareholder_count,source_id))
        connection.commit()
    return {"status":"completed", "symbol":symbol, "fundamental_rows":len(parsed.fundamental_values), "shareholding_rows":len(parsed.shareholding), "warnings":len(parsed.warnings), "force":force}
