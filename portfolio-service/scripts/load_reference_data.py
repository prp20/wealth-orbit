"""Load non-historical stock and mutual-fund reference data into Supabase."""
from __future__ import annotations

import argparse
import csv
import os
import sys
import uuid
from pathlib import Path

import psycopg2
from psycopg2.extras import register_uuid
from psycopg2.extras import execute_values
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
register_uuid()


def get_or_create(cur, table, key_column, key_value, insert_columns, insert_values, id_column):
    cur.execute(f"SELECT {id_column} FROM market_data.{table} WHERE {key_column} = %s", (key_value,))
    row = cur.fetchone()
    if row:
        return row[0]
    new_id = uuid.uuid4()
    columns = ", ".join([id_column, *insert_columns])
    placeholders = ", ".join(["%s"] * (1 + len(insert_values)))
    cur.execute(f"INSERT INTO market_data.{table} ({columns}) VALUES ({placeholders})", (new_id, *insert_values))
    return new_id


def load_stocks(cur, path: Path) -> tuple[int, int]:
    inserted = 0
    indexes = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            symbol = (row.get("symbol") or "").strip()
            company = (row.get("company_name") or symbol).strip()
            if not symbol:
                continue
            sector_name = (row.get("sector") or "Unclassified").strip()
            industry_name = (row.get("industry") or "Unclassified").strip()
            sector_id = get_or_create(cur, "sector_reference", "sector_name", sector_name, ["sector_name"], [sector_name], "sector_id")
            cur.execute("SELECT industry_id FROM market_data.industry_reference WHERE sector_id = %s AND industry_name = %s", (sector_id, industry_name))
            industry = cur.fetchone()
            if industry:
                industry_id = industry[0]
            else:
                industry_id = uuid.uuid4()
                cur.execute("INSERT INTO market_data.industry_reference (industry_id, sector_id, industry_name) VALUES (%s, %s, %s)", (industry_id, sector_id, industry_name))
            cur.execute("SELECT stock_id FROM market_data.stock_reference WHERE exchange = %s AND trading_symbol = %s", ("NSE", symbol))
            if not cur.fetchone():
                cur.execute("INSERT INTO market_data.stock_reference (stock_id, trading_symbol, exchange, company_name, sector_id, industry_id) VALUES (%s, %s, %s, %s, %s, %s)", (uuid.uuid4(), symbol, "NSE", company, sector_id, industry_id))
                inserted += 1
            if (row.get("is_index") or "").strip().lower() == "true":
                index_name = (row.get("market_cap_category") or symbol).strip()
                cur.execute("SELECT index_id FROM market_data.index_reference WHERE index_code = %s", (index_name,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO market_data.index_reference (index_id, index_name, index_code) VALUES (%s, %s, %s)", (uuid.uuid4(), index_name, index_name))
                    indexes += 1
    return inserted, indexes


def load_mutual_funds(cur, path: Path) -> int:
    inserted = 0
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            scheme_code = (row.get("scheme_code") or "").strip() or None
            scheme_name = (row.get("scheme_name") or "").strip()
            if not scheme_name:
                continue
            amc_name = (row.get("amc_name") or "Unknown AMC").strip()
            category_name = (row.get("scheme_category") or "Unclassified").strip()
            subcategory_name = (row.get("scheme_subcategory") or "Unclassified").strip()
            amc_id = get_or_create(cur, "amc_reference", "amc_name", amc_name, ["amc_name"], [amc_name], "amc_id")
            category_id = get_or_create(cur, "mutual_fund_categories", "category_name", category_name, ["category_name"], [category_name], "category_id")
            cur.execute("SELECT subcategory_id FROM market_data.mutual_fund_subcategories WHERE category_id = %s AND subcategory_name = %s", (category_id, subcategory_name))
            found = cur.fetchone()
            if found:
                subcategory_id = found[0]
            else:
                subcategory_id = uuid.uuid4()
                cur.execute("INSERT INTO market_data.mutual_fund_subcategories (subcategory_id, category_id, subcategory_name) VALUES (%s, %s, %s)", (subcategory_id, category_id, subcategory_name))
            benchmark = (row.get("benchmark_index_code") or "").strip() or None
            benchmark_id = None
            if benchmark:
                benchmark_id = get_or_create(cur, "index_reference", "index_code", benchmark, ["index_name", "index_code"], [benchmark, benchmark], "index_id")
            plan = "DIRECT" if (row.get("plan_type") or "").strip().lower() == "direct" else "REGULAR"
            option = "IDCW" if any(word in scheme_name.lower() for word in ("idcw", "dividend", "income distribution")) else "GROWTH"
            cur.execute("SELECT scheme_id FROM market_data.mutual_fund_reference WHERE scheme_code = %s", (scheme_code,)) if scheme_code else cur.execute("SELECT scheme_id FROM market_data.mutual_fund_reference WHERE scheme_name = %s", (scheme_name,))
            if not cur.fetchone():
                cur.execute("INSERT INTO market_data.mutual_fund_reference (scheme_id, scheme_code, scheme_name, amc_id, subcategory_id, benchmark_index_id, plan_type, option_type) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (uuid.uuid4(), scheme_code, scheme_name, amc_id, subcategory_id, benchmark_id, plan, option))
                inserted += 1
    return inserted


def bulk_load(cur, stocks_path: Path, funds_path: Path):
    with stocks_path.open(newline="", encoding="utf-8-sig") as f:
        stocks = list(csv.DictReader(f))
    with funds_path.open(newline="", encoding="utf-8-sig") as f:
        funds = list(csv.DictReader(f))
    sectors = {}
    industries = {}
    indexes = {}
    for row in stocks:
        sector = (row.get("sector") or "Unclassified").strip()
        industry = (row.get("industry") or "Unclassified").strip()
        sectors.setdefault(sector, uuid.uuid4())
        industries.setdefault((sector, industry), uuid.uuid4())
        if (row.get("is_index") or "").strip().lower() == "true":
            code = (row.get("market_cap_category") or row.get("symbol") or "").strip()
            if code: indexes.setdefault(code, uuid.uuid4())
    for row in funds:
        code = (row.get("benchmark_index_code") or "").strip()
        if code: indexes.setdefault(code, uuid.uuid4())
    amcs = {(row.get("amc_name") or "Unknown AMC").strip(): uuid.uuid4() for row in funds}
    categories = {(row.get("scheme_category") or "Unclassified").strip(): uuid.uuid4() for row in funds}
    subcategories = {}
    for row in funds:
        category = (row.get("scheme_category") or "Unclassified").strip()
        sub = (row.get("scheme_subcategory") or "Unclassified").strip()
        subcategories.setdefault((category, sub), uuid.uuid4())
    print("sectors", len(sectors), flush=True)
    execute_values(cur, "INSERT INTO market_data.sector_reference (sector_id, sector_name) VALUES %s ON CONFLICT (sector_name) DO NOTHING", [(v, k) for k, v in sectors.items()])
    print("industries", len(industries), flush=True)
    execute_values(cur, "INSERT INTO market_data.industry_reference (industry_id, sector_id, industry_name) VALUES %s ON CONFLICT (sector_id, industry_name) DO NOTHING", [(v, sectors[s], i) for (s, i), v in industries.items()])
    print("indexes", len(indexes), flush=True)
    execute_values(cur, "INSERT INTO market_data.index_reference (index_id, index_name, index_code) VALUES %s ON CONFLICT (index_code) DO NOTHING", [(v, k, k) for k, v in indexes.items()])
    print("amcs/categories/subcategories", len(amcs), len(categories), len(subcategories), flush=True)
    execute_values(cur, "INSERT INTO market_data.amc_reference (amc_id, amc_name) VALUES %s ON CONFLICT (amc_name) DO NOTHING", [(v, k) for k, v in amcs.items()])
    execute_values(cur, "INSERT INTO market_data.mutual_fund_categories (category_id, category_name) VALUES %s ON CONFLICT (category_name) DO NOTHING", [(v, k) for k, v in categories.items()])
    execute_values(cur, "INSERT INTO market_data.mutual_fund_subcategories (subcategory_id, category_id, subcategory_name) VALUES %s ON CONFLICT (category_id, subcategory_name) DO NOTHING", [(v, categories[c], s) for (c, s), v in subcategories.items()])
    stock_rows = []
    for row in stocks:
        symbol = (row.get("symbol") or "").strip()
        if symbol:
            sector = (row.get("sector") or "Unclassified").strip()
            industry = (row.get("industry") or "Unclassified").strip()
            stock_rows.append((uuid.uuid4(), symbol, "NSE", (row.get("company_name") or symbol).strip(), sectors[sector], industries[(sector, industry)]))
    execute_values(cur, "INSERT INTO market_data.stock_reference (stock_id, trading_symbol, exchange, company_name, sector_id, industry_id) VALUES %s ON CONFLICT (exchange, trading_symbol) DO NOTHING", stock_rows, page_size=500)
    fund_rows = []
    for row in funds:
        name = (row.get("scheme_name") or "").strip()
        if not name: continue
        category = (row.get("scheme_category") or "Unclassified").strip()
        sub = (row.get("scheme_subcategory") or "Unclassified").strip()
        benchmark = (row.get("benchmark_index_code") or "").strip() or None
        plan = "DIRECT" if (row.get("plan_type") or "").strip().lower() == "direct" else "REGULAR"
        option = "IDCW" if any(x in name.lower() for x in ("idcw", "dividend", "income distribution")) else "GROWTH"
        fund_rows.append((uuid.uuid4(), (row.get("scheme_code") or "").strip() or None, name, amcs[(row.get("amc_name") or "Unknown AMC").strip()], subcategories[(category, sub)], indexes.get(benchmark), plan, option))
    execute_values(cur, "INSERT INTO market_data.mutual_fund_reference (scheme_id, scheme_code, scheme_name, amc_id, subcategory_id, benchmark_index_id, plan_type, option_type) VALUES %s ON CONFLICT (scheme_code) DO NOTHING", fund_rows, page_size=500)
    return len(stock_rows), len(fund_rows), len(indexes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stocks", type=Path, required=True)
    parser.add_argument("--mutual-funds", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ["DATABASE_URL"]
    with psycopg2.connect(url) as connection:
        with connection.cursor() as cur:
            stocks, funds, indexes = bulk_load(cur, args.stocks, args.mutual_funds)
        connection.commit()
    print(f"Loaded {stocks} stocks, {indexes} index references, and {funds} mutual-fund schemes")


if __name__ == "__main__":
    main()
