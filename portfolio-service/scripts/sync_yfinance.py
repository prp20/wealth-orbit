"""Sync daily OHLCV history for Supabase stock references via yfinance."""
import argparse
import os
import uuid
import warnings
from datetime import date

import psycopg2
import yfinance as yf
warnings.filterwarnings("ignore", message=".*inplace keyword.*", category=Warning)
from dotenv import load_dotenv
from psycopg2.extras import execute_values, register_uuid

load_dotenv()
register_uuid()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", default="1y", help="yfinance period, for example 1y or max")
    parser.add_argument("--source-name", default="yfinance")
    parser.add_argument("--force", action="store_true", help="rewrite dates already present")
    args = parser.parse_args()
    with psycopg2.connect(os.environ["DATABASE_URL"]) as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT stock_id, trading_symbol FROM market_data.stock_reference WHERE is_active = TRUE ORDER BY trading_symbol")
            stocks = cur.fetchall()
            source_id = uuid.uuid4()
            cur.execute("SELECT source_id FROM market_data.data_sources WHERE source_name=%s", (args.source_name,))
            found = cur.fetchone()
            if found: source_id = found[0]
            else: cur.execute("INSERT INTO market_data.data_sources(source_id, source_name) VALUES(%s,%s)", (source_id, args.source_name))
            rows = []
            for position, (stock_id, symbol) in enumerate(stocks, 1):
                print(f"[{position}/{len(stocks)}] {symbol}", flush=True)
                ticker = yf.Ticker(f"{symbol}.NS")
                history = ticker.history(period=args.period, auto_adjust=False)
                existing = set()
                if not args.force:
                    cur.execute("SELECT trading_date FROM market_data.stock_daily_prices WHERE stock_id=%s", (stock_id,))
                    existing = {row[0] for row in cur.fetchall()}
                for timestamp, values in history.iterrows():
                    if values[["Open", "High", "Low", "Close"]].isna().any(): continue
                    trading_date = timestamp.date()
                    if trading_date in existing: continue
                    rows.append((stock_id, trading_date, float(values["Open"]), float(values["High"]), float(values["Low"]), float(values["Close"]), int(values.get("Volume", 0)), source_id))
            execute_values(cur, """INSERT INTO market_data.stock_daily_prices(stock_id,trading_date,open,high,low,close,volume,source_id) VALUES %s ON CONFLICT(stock_id,trading_date) DO UPDATE SET open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,close=EXCLUDED.close,volume=EXCLUDED.volume,source_id=EXCLUDED.source_id,updated_at=NOW()""", rows, page_size=1000)
        connection.commit()
    print(f"Synced {len(rows)} daily OHLCV observations for {len(stocks)} stocks")


if __name__ == "__main__": main()
