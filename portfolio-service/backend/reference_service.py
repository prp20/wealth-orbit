"""Read-only access to Supabase market_data reference tables."""
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def _query(sql: str, params=()) -> pd.DataFrame:
    with psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [item[0] for item in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=columns)


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

def stock_history(symbol: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("SELECT p.trading_date AS date,p.open,p.high,p.low,p.close,p.volume FROM market_data.stock_daily_prices p JOIN market_data.stock_reference s ON s.stock_id=p.stock_id WHERE s.trading_symbol=%s AND (%s IS NULL OR p.trading_date >= %s) AND (%s IS NULL OR p.trading_date <= %s) ORDER BY p.trading_date", (symbol, from_date, from_date, to_date, to_date))

def mutual_fund_history(scheme_code: str, from_date=None, to_date=None) -> pd.DataFrame:
    return _query("SELECT h.nav_date AS date,h.nav FROM market_data.mutual_fund_nav_history h JOIN market_data.mutual_fund_reference m ON m.scheme_id=h.scheme_id WHERE m.scheme_code=%s AND (%s IS NULL OR h.nav_date >= %s) AND (%s IS NULL OR h.nav_date <= %s) ORDER BY h.nav_date", (scheme_code, from_date, from_date, to_date, to_date))
