"""
run_all_seeds.py — Orchestrate Wealth Orbit market-data seed pipelines.

Prefer the asset-specific entrypoints when you only need one domain:
  - run_seed_indexes.py
  - run_seed_stocks.py   (OHLC by default; add --with-fundamentals / --with-technicals for latest technicals + metrics)
  - run_seed_funds.py

This script runs all three in dependency-friendly order:
  1. Indexes (masters + history)
  2. Stocks (masters + OHLC; fundamentals/technicals optional)
  3. Mutual funds (masters + NAV)

Prerequisites:
  - Alembic migrations applied; base market_data tables present in Postgres
  - DATABASE_URL set (Supabase pooler URL)
  - Seed CSVs under data/seed/ (or pass --data-dir)

Usage:
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --data-dir data/seed --skip-prices --skip-nav --limit 50
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only stocks --with-fundamentals --limit 3
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only stocks --with-technicals --limit 10
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only funds --limit 10
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only indexes --index-period 5y
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_fund_nav
import seed_fundamentals
import seed_funds
import seed_index_history
import seed_indexes
import seed_stock_prices
import seed_stock_technicals
import seed_stocks
from _db import resolve_data_dir


def _seed_indexes(args, data_dir: Path) -> None:
    print("\n--- Indexes ---")
    if not args.skip_masters:
        print("[indexes] masters")
        seed_indexes.seed(data_dir=data_dir, dry_run=args.dry_run)
    if not args.skip_index_history:
        print("[indexes] history (Yahoo OHLC)")
        seed_index_history.seed(period=args.index_period, dry_run=args.dry_run, limit=args.limit)


def _seed_stocks(args, data_dir: Path) -> None:
    print("\n--- Stocks ---")
    master_symbols: list[str] | None = None
    if not args.skip_masters:
        print("[stocks] masters")
        masters = seed_stocks.seed(data_dir=data_dir, dry_run=args.dry_run, limit=args.limit)
        master_symbols = list(masters.get("symbols") or [])
    if not args.skip_prices:
        print("[stocks] OHLC prices (Yahoo)")
        seed_stock_prices.seed(
            period=args.price_period,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=None if master_symbols is not None else args.limit,
            data_dir=data_dir,
            symbols=master_symbols,
        )
    if args.with_fundamentals and not args.skip_fundamentals:
        print("[stocks] fundamentals + shareholding (Screener)")
        seed_fundamentals.seed(
            dry_run=args.dry_run,
            limit=None if master_symbols is not None else args.limit,
            delay_secs=args.fundamentals_delay,
            symbols=master_symbols,
        )
    elif not args.skip_fundamentals:
        print("[stocks] fundamentals skipped (pass --with-fundamentals to enable)")
    if args.with_technicals:
        print("[stocks] latest-day technicals + daily metrics (Yahoo)")
        seed_stock_technicals.seed(
            dry_run=args.dry_run,
            limit=None if master_symbols is not None else args.limit,
            delay_secs=args.technicals_delay,
            symbols=master_symbols,
            workers=args.technicals_workers,
        )
    else:
        print("[stocks] technicals/metrics skipped (pass --with-technicals to enable)")


def _seed_funds(args, data_dir: Path) -> None:
    print("\n--- Mutual funds ---")
    master_scheme_codes: list[str] | None = None
    if not args.skip_masters:
        print("[funds] masters")
        masters = seed_funds.seed(data_dir=data_dir, dry_run=args.dry_run, limit=args.limit)
        master_scheme_codes = list(masters.get("scheme_codes") or [])
    if not args.skip_nav:
        print("[funds] NAV history (mftool/MFAPI)")
        seed_fund_nav.seed(
            dry_run=args.dry_run,
            limit=None if master_scheme_codes is not None else args.limit,
            scheme_codes=master_scheme_codes,
            history_period=args.nav_period,
        )


def main():
    parser = argparse.ArgumentParser(description="Run market-data seed pipelines")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory with seed CSVs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--only",
        choices=("all", "indexes", "stocks", "funds"),
        default="all",
        help="Run a single asset pipeline or all (default)",
    )
    parser.add_argument("--price-period", default="10y", help="yfinance period for stock prices")
    parser.add_argument("--index-period", default="10y", help="yfinance period for index history (default 10y)")
    parser.add_argument(
        "--nav-period",
        default="10y",
        choices=["1y", "2y", "3y", "5y", "10y", "max"],
        help="NAV retention after sync (default 10y)",
    )
    parser.add_argument("--batch-size", type=int, default=20, help="Stock price download batch size")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap masters and the matching OHLC/NAV/fundamentals universe",
    )
    parser.add_argument("--skip-masters", action="store_true")
    parser.add_argument("--skip-index-history", action="store_true")
    parser.add_argument("--skip-prices", action="store_true", help="Skip stock OHLC")
    parser.add_argument("--skip-nav", action="store_true")
    parser.add_argument(
        "--with-fundamentals",
        action="store_true",
        help="Include Screener fundamentals when seeding stocks (off by default)",
    )
    parser.add_argument(
        "--skip-fundamentals",
        action="store_true",
        help="Deprecated alias: fundamentals are already off unless --with-fundamentals",
    )
    parser.add_argument(
        "--with-technicals",
        action="store_true",
        help="Include latest-day technicals + Yahoo daily metrics (off by default)",
    )
    parser.add_argument(
        "--fundamentals-delay",
        type=float,
        default=3.0,
        help="Seconds between Screener fundamentals calls",
    )
    parser.add_argument(
        "--technicals-delay",
        type=float,
        default=0.0,
        help="Per-worker pause after each technicals/metrics symbol (default 0)",
    )
    parser.add_argument(
        "--technicals-workers",
        type=int,
        default=8,
        help="Parallel workers for technicals/metrics sync (default 8)",
    )
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    print("\n" + "=" * 50)
    print("Wealth Orbit — Market Data Seeding")
    print(f"data-dir: {data_dir}")
    print(f"only: {args.only}")
    print("=" * 50)

    if args.only in {"all", "indexes"}:
        _seed_indexes(args, data_dir)
    if args.only in {"all", "stocks"}:
        _seed_stocks(args, data_dir)
    if args.only in {"all", "funds"}:
        _seed_funds(args, data_dir)

    print("\n" + "=" * 50)
    if args.dry_run:
        print("DRY RUN complete — no data written.")
    else:
        print("Seeding complete.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
