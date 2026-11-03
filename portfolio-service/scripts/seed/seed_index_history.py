"""Seed index_daily_history from Yahoo Finance using index_provider_mappings."""
from __future__ import annotations

import argparse
import time

import yfinance as yf
from psycopg2.extras import execute_values

from _db import connect, ensure_project_paths, get_or_create_source

ensure_project_paths()

from backend.market_data.index_history import quote_identifier, resolve_index_history_columns


def _table_columns(cur) -> set[str]:
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema='market_data' AND table_name='index_daily_history'"""
    )
    return {row[0] for row in cur.fetchall()}


def _download_history(ticker: str, period: str) -> list[tuple]:
    try:
        frame = yf.download(
            ticker,
            period=period,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        print(f"  yf.download error for {ticker}: {exc}")
        return []
    if frame is None or frame.empty:
        return []
    if hasattr(frame.columns, "get_level_values") and getattr(frame.columns, "nlevels", 1) > 1:
        frame.columns = frame.columns.get_level_values(0)
    if "Close" not in frame.columns:
        return []
    rows = []
    for timestamp, close in frame["Close"].items():
        if close != close:  # NaN
            continue
        try:
            history_date = timestamp.date()
        except AttributeError:
            history_date = timestamp
        close_value = float(close)
        if close_value <= 0:
            continue
        open_value = float(frame.at[timestamp, "Open"]) if "Open" in frame.columns else close_value
        high_value = float(frame.at[timestamp, "High"]) if "High" in frame.columns else close_value
        low_value = float(frame.at[timestamp, "Low"]) if "Low" in frame.columns else close_value
        volume = None
        if "Volume" in frame.columns:
            try:
                volume = int(frame.at[timestamp, "Volume"])
            except (TypeError, ValueError):
                volume = None
        rows.append((history_date, open_value, high_value, low_value, close_value, volume))
    return rows


def seed(period: str = "max", dry_run: bool = False, limit: int | None = None) -> dict:
    with connect() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """SELECT m.index_id, i.index_code, m.trading_symbol
                   FROM market_data.index_provider_mappings m
                   JOIN market_data.index_reference i ON i.index_id = m.index_id
                   WHERE m.provider = 'yfinance' AND m.is_active = TRUE
                   ORDER BY i.index_code"""
            )
            benchmarks = cur.fetchall()
            if limit is not None:
                benchmarks = benchmarks[:limit]
            if not benchmarks:
                print("  No yfinance index mappings found. Run seed_indexes.py first.")
                return {"indexes": 0, "rows": 0}

            date_col, _close_col = resolve_index_history_columns(cur)
            columns = _table_columns(cur)
            include_volume = "volume" in columns
            date_identifier = quote_identifier(date_col)

            print(f"  Found {len(benchmarks)} indexes — fetching '{period}' history "
                  f"(date column={date_col})")
            source_id = None if dry_run else get_or_create_source(cur, "yfinance")
            total_rows = 0
            failed = []

            if include_volume:
                insert_sql = f"""INSERT INTO market_data.index_daily_history
                   (index_id, {date_identifier}, open, high, low, close, volume, source_id)
                   VALUES %s
                   ON CONFLICT (index_id, {date_identifier}) DO UPDATE
                   SET open = EXCLUDED.open,
                       high = EXCLUDED.high,
                       low = EXCLUDED.low,
                       close = EXCLUDED.close,
                       volume = EXCLUDED.volume,
                       source_id = EXCLUDED.source_id,
                       updated_at = NOW()"""
            else:
                insert_sql = f"""INSERT INTO market_data.index_daily_history
                   (index_id, {date_identifier}, open, high, low, close, source_id)
                   VALUES %s
                   ON CONFLICT (index_id, {date_identifier}) DO UPDATE
                   SET open = EXCLUDED.open,
                       high = EXCLUDED.high,
                       low = EXCLUDED.low,
                       close = EXCLUDED.close,
                       source_id = EXCLUDED.source_id,
                       updated_at = NOW()"""

            for index_id, index_code, ticker in benchmarks:
                print(f"  [{index_code}] ticker={ticker!r}", end="", flush=True)
                rows = _download_history(ticker, period)
                if not rows:
                    print("  ← no data")
                    failed.append(index_code)
                    time.sleep(0.3)
                    continue
                print(f"  {len(rows)} rows ({rows[0][0]} → {rows[-1][0]})", end="", flush=True)
                if dry_run:
                    print("  [DRY RUN]")
                    total_rows += len(rows)
                    time.sleep(0.3)
                    continue
                if include_volume:
                    values = [
                        (index_id, history_date, open_, high, low, close, volume, source_id)
                        for history_date, open_, high, low, close, volume in rows
                    ]
                else:
                    values = [
                        (index_id, history_date, open_, high, low, close, source_id)
                        for history_date, open_, high, low, close, _volume in rows
                    ]
                execute_values(cur, insert_sql, values, page_size=1000)
                total_rows += len(values)
                print("  ok")
                time.sleep(0.3)
        connection.commit()

    print(f"  {'Would upsert' if dry_run else 'Upserted'} {total_rows} index history rows "
          f"({len(failed)} failed)")
    return {"indexes": len(benchmarks) - len(failed), "rows": total_rows, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Seed index_daily_history from Yahoo Finance")
    parser.add_argument("--period", default="max")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    print("=== Seeding index history ===")
    seed(period=args.period, dry_run=args.dry_run, limit=args.limit)
    print("Done.")


if __name__ == "__main__":
    main()
