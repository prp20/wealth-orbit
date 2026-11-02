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


def mutual_funds(search: str = "", category: str = "All") -> pd.DataFrame:
    return _query("""
        SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name,
               s.subcategory_name, m.plan_type, m.option_type,
               m.is_active
        FROM market_data.mutual_fund_reference m
        JOIN market_data.amc_reference a ON a.amc_id = m.amc_id
        JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id = m.subcategory_id
        JOIN market_data.mutual_fund_categories c ON c.category_id = s.category_id
        WHERE (%s = '' OR m.scheme_name ILIKE %s OR m.scheme_code ILIKE %s)
          AND (%s = 'All' OR c.category_name = %s)
        ORDER BY m.scheme_name
    """, (search, f"%{search}%", f"%{search}%", category, category))


def stock_categories() -> list[str]:
    return _query("SELECT DISTINCT sector_name FROM market_data.sector_reference ORDER BY sector_name")["sector_name"].tolist()


def stocks(search: str = "", sector: str = "All") -> pd.DataFrame:
    return _query("""
        SELECT s.trading_symbol, s.company_name, s.exchange,
               sr.sector_name, ir.industry_name, s.is_active
        FROM market_data.stock_reference s
        LEFT JOIN market_data.sector_reference sr ON sr.sector_id = s.sector_id
        LEFT JOIN market_data.industry_reference ir ON ir.industry_id = s.industry_id
        WHERE (%s = '' OR s.trading_symbol ILIKE %s OR s.company_name ILIKE %s)
          AND (%s = 'All' OR sr.sector_name = %s)
        ORDER BY s.trading_symbol
    """, (search, f"%{search}%", f"%{search}%", sector, sector))


def stock_detail(symbol: str):
    frame = _query("SELECT s.trading_symbol, s.company_name, s.exchange, sr.sector_name, ir.industry_name, s.is_active FROM market_data.stock_reference s LEFT JOIN market_data.sector_reference sr ON sr.sector_id=s.sector_id LEFT JOIN market_data.industry_reference ir ON ir.industry_id=s.industry_id WHERE s.trading_symbol=%s", (symbol,))
    return None if frame.empty else frame.iloc[0].to_dict()


def mutual_fund_detail(scheme_code: str):
    frame = _query("""SELECT m.scheme_code, m.scheme_name, a.amc_name, c.category_name, s.subcategory_name, m.plan_type, m.option_type, m.is_active FROM market_data.mutual_fund_reference m JOIN market_data.amc_reference a ON a.amc_id=m.amc_id JOIN market_data.mutual_fund_subcategories s ON s.subcategory_id=m.subcategory_id JOIN market_data.mutual_fund_categories c ON c.category_id=s.category_id WHERE m.scheme_code=%s""", (scheme_code,))
    return None if frame.empty else frame.iloc[0].to_dict()
