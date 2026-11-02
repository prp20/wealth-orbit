"""Read-only access to Supabase market_data reference tables."""
import os
import pandas as pd
import psycopg2
from psycopg2.extras import register_uuid
from dotenv import load_dotenv

load_dotenv()
register_uuid()


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


def mutual_fund_detail(scheme_code: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_code=%s""", (scheme_code,))
    return None if frame.empty else frame.iloc[0].to_dict()

def mutual_fund_detail_by_name(name: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_name=%s""", (name,))
    return None if frame.empty else frame.iloc[0].to_dict()

def mutual_fund_similar(scheme_code: str) -> pd.DataFrame:
    return _query("""SELECT m2.scheme_code,m2.scheme_name,a.amc_name,c.category_name,s.subcategory_name,m2.plan_type,m2.option_type
      FROM market_data.mutual_fund_reference m1 JOIN market_data.mutual_fund_reference m2 ON m2.subcategory_id=m1.subcategory_id
      JOIN market_data.amc_reference a ON a.amc_id=m2.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m2.subcategory_id
      JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m1.scheme_code=%s AND m2.scheme_code<>%s AND m2.is_active=TRUE ORDER BY m2.scheme_name LIMIT 20""", (scheme_code,scheme_code))

def stock_history(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("SELECT p.trading_date AS date,p.open,p.high,p.low,p.close,p.volume FROM market_data.stock_daily_prices p JOIN market_data.stock_reference s ON s.stock_id=p.stock_id WHERE s.trading_symbol=%s AND (%s IS NULL OR p.trading_date >= %s) AND (%s IS NULL OR p.trading_date <= %s) ORDER BY p.trading_date", (symbol, from_date, from_date, to_date, to_date))

def mutual_fund_history(scheme_code: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("SELECT h.nav_date AS date,h.nav FROM market_data.mutual_fund_nav_history h JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id WHERE m.scheme_code=%s AND (%s IS NULL OR h.nav_date >= %s) AND (%s IS NULL OR h.nav_date <= %s) ORDER BY h.nav_date", (scheme_code, from_date, from_date, to_date, to_date))

def stock_daily_metrics(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("""SELECT m.metric_date AS date, m.market_cap, m.stock_pe, m.price_to_book,
        m.dividend_yield, m.book_value, m.roce, m.roe, m.calculation_method
        FROM market_data.stock_daily_metrics m
        JOIN market_data.stock_reference s ON s.stock_id=m.stock_id
        WHERE s.trading_symbol=%s AND (%s IS NULL OR m.metric_date >= %s)
          AND (%s IS NULL OR m.metric_date <= %s) ORDER BY m.metric_date""",
        (symbol, from_date, from_date, to_date, to_date))

def stock_fundamentals(symbol: str, reporting_period: str = "", reporting_basis: str = "", metric_code: str = "") -> pd.DataFrame:
    return _query("""SELECT v.period_end_date, v.period_start_date, v.reporting_period,
        v.reporting_basis, r.metric_code, r.metric_name, r.statement_type, r.unit,
        v.metric_value, v.source_id
        FROM market_data.stock_fundamental_values v
        JOIN market_data.stock_reference s ON s.stock_id=v.stock_id
        JOIN market_data.fundamental_metric_reference r ON r.metric_id=v.metric_id
        WHERE s.trading_symbol=%s AND (%s='' OR v.reporting_period=%s)
          AND (%s='' OR v.reporting_basis=%s) AND (%s='' OR r.metric_code=%s)
        ORDER BY v.period_end_date DESC, r.metric_code""",
        (symbol, reporting_period, reporting_period, reporting_basis, reporting_basis, metric_code, metric_code))

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
    """Fetch Screener consolidated data and upsert canonical fundamentals."""
    from backend.market_data.providers.screener import ScreenerParser, build_company_url, fetch_html
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE trading_symbol=%s AND is_active=TRUE", (symbol,))
            row = cur.fetchone()
            if not row: raise ValueError(f"Active stock not found: {symbol}")
            stock_id = row[0]
            html = fetch_html(build_company_url(symbol, None), "Mozilla/5.0 (compatible; WealthOrbit/1.0)")
            if not html: return {"status":"failed", "symbol":symbol, "reason":"Screener returned no HTML"}
            parsed = ScreenerParser().parse(html, stock_id)
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
