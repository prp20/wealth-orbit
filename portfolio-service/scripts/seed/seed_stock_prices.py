"""Seed stock_daily_prices from Yahoo Finance in batches."""
from __future__ import annotations

import argparse
import csv
import math
import time
from pathlib import Path

import yfinance as yf
from psycopg2.extras import execute_values

from _db import connect, get_or_create_source, resolve_data_dir

BATCH_DELAY_SECS = 1.5
MAX_RETRIES = 3


def _scalar(value):
    if hasattr(value, "iloc"):
        value = value.iloc[0]
    return value


def _safe_float(value) -> float | None:
    try:
        number = float(_scalar(value))
        return None if math.isnan(number) else number
    except (TypeError, ValueError):
        return None


def _safe_int(value) -> int | None:
    try:
        return int(_scalar(value))
    except (TypeError, ValueError):
        return None


def _yf_lookup(data_dir: Path | None) -> dict[str, str]:
    """Map trading_symbol -> yf_symbol from stocks.csv when available."""
    if data_dir is None:
        return {}
    path = resolve_data_dir(data_dir) / "stocks.csv"
    if not path.exists():
        return {}
    lookup = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if str(row.get("is_index") or "").strip().lower() in {"true", "1", "yes"}:
                continue
            symbol = (row.get("symbol") or "").strip()
            yf_symbol = (row.get("yf_symbol") or "").strip()
            if symbol and yf_symbol:
                lookup[symbol] = yf_symbol
    return lookup


def _download_batch(tickers: list[str], period: str) -> dict:
    if not tickers:
        return {}
    raw = None
    for attempt in range(MAX_RETRIES):
        try:
            raw = yf.download(
                tickers,
                period=period,
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            break
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"  Batch download failed after {MAX_RETRIES} attempts: {exc}")
                return {}
            time.sleep(2 ** attempt)
    if raw is None or raw.empty:
        return {}
    result = {}
    if len(tickers) == 1:
        result[tickers[0]] = raw
        return result
    for ticker in tickers:
        try:
            frame = raw.xs(ticker, axis=1, level=1).dropna(subset=["Close"])
            if not frame.empty:
                result[ticker] = frame
        except (KeyError, TypeError):
            continue
    return result


def _build_rows(stock_id, frame, source_id) -> list[tuple]:
    rows = []
    for timestamp, values in frame.iterrows():
        open_ = _safe_float(values.get("Open"))
        high = _safe_float(values.get("High"))
        low = _safe_float(values.get("Low"))
        close = _safe_float(values.get("Close"))
        if None in (open_, high, low, close):
            continue
        rows.append(
            (
                stock_id,
                timestamp.date(),
                open_,
                high,
                low,
                close,
                _safe_int(values.get("Volume")) or 0,
                source_id,
            )
        )
    return rows


def seed(
    period: str = "5y",
    dry_run: bool = False,
    batch_size: int = 20,
    limit: int | None = None,
    data_dir: Path | str | None = None,
) -> dict:
    yf_lookup = _yf_lookup(Path(data_dir) if data_dir else None)
    with connect() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """SELECT stock_id, trading_symbol
                   FROM market_data.stock_reference
                   WHERE is_active = TRUE
                   ORDER BY trading_symbol"""
            )
            stocks = cur.fetchall()
            if limit is not None:
                stocks = stocks[:limit]
            if not stocks:
                print("  No active stocks found. Run seed_stocks.py first.")
                return {"stocks": 0, "rows": 0}

            source_id = None if dry_run else get_or_create_source(cur, "yfinance")
            enriched = []
            for stock_id, symbol in stocks:
                yf_symbol = yf_lookup.get(symbol) or f"{symbol}.NS"
                enriched.append((stock_id, symbol, yf_symbol))

            print(
                f"  Fetching {period} prices for {len(enriched)} stocks "
                f"(batch_size={batch_size}){'  [DRY RUN]' if dry_run else ''}"
            )
            yf_to_stock = {yf_symbol: stock_id for stock_id, _, yf_symbol in enriched}
            tickers = [yf_symbol for _, _, yf_symbol in enriched]
            batches = [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]
            total_rows = 0
            failed = []

            for position, batch in enumerate(batches, 1):
                print(f"  Batch {position}/{len(batches)} ({len(batch)} tickers)", flush=True)
                data = _download_batch(batch, period)
                batch_rows = []
                for yf_symbol in batch:
                    frame = data.get(yf_symbol)
                    if frame is None or frame.empty:
                        failed.append(yf_symbol)
                        continue
                    batch_rows.extend(_build_rows(yf_to_stock[yf_symbol], frame, source_id))
                if dry_run:
                    total_rows += len(batch_rows)
                elif batch_rows:
                    execute_values(
                        cur,
                        """INSERT INTO market_data.stock_daily_prices
                           (stock_id, trading_date, open, high, low, close, volume, source_id)
                           VALUES %s
                           ON CONFLICT (stock_id, trading_date) DO UPDATE
                           SET open = EXCLUDED.open,
                               high = EXCLUDED.high,
                               low = EXCLUDED.low,
                               close = EXCLUDED.close,
                               volume = EXCLUDED.volume,
                               source_id = EXCLUDED.source_id,
                               updated_at = NOW()""",
                        batch_rows,
                        page_size=1000,
                    )
                    total_rows += len(batch_rows)
                time.sleep(BATCH_DELAY_SECS)
        connection.commit()

    print(
        f"  {'Would upsert' if dry_run else 'Upserted'} {total_rows} price rows "
        f"across {len(enriched) - len(failed)} stocks"
    )
    if failed:
        preview = ", ".join(failed[:20])
        suffix = " ..." if len(failed) > 20 else ""
        print(f"  No data for {len(failed)} symbols: {preview}{suffix}")
    return {"stocks": len(enriched) - len(failed), "rows": total_rows, "failed": failed}


def main():
    parser = argparse.ArgumentParser(description="Seed stock_daily_prices from Yahoo Finance")
    parser.add_argument("--period", default="5y", choices=["1y", "2y", "3y", "5y", "10y", "max"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    args = parser.parse_args()
    print("=== Seeding stock prices ===")
    seed(
        period=args.period,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        limit=args.limit,
        data_dir=args.data_dir,
    )
    print("Done.")


if __name__ == "__main__":
    main()
