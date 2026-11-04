"""
run_all_seeds.py — Orchestrate Wealth Orbit market-data seed pipelines.

Prefer the asset-specific entrypoints when you only need one domain:
  - run_seed_indexes.py
  - run_seed_stocks.py   (OHLC by default; add --with-fundamentals for Screener)
  - run_seed_funds.py

This script runs all three in dependency-friendly order:
  1. Indexes (masters + history)
  2. Stocks (masters + OHLC; fundamentals optional)
  3. Mutual funds (masters + NAV)

Prerequisites:
  - Alembic migrations applied; base market_data tables present in Postgres
  - DATABASE_URL set (Supabase pooler URL)
  - Seed CSVs under data/seed/ (or pass --data-dir)

Usage:
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --data-dir data/seed --dry-run
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only stocks --with-fundamentals --limit 3
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only funds --limit 10
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --only indexes
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
    if not args.skip_masters:
        print("[stocks] masters")
        seed_stocks.seed(data_dir=data_dir, dry_run=args.dry_run)
    if not args.skip_prices:
        print("[stocks] OHLC prices (Yahoo)")
        seed_stock_prices.seed(
            period=args.price_period,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit,
            data_dir=data_dir,
        )
    if args.with_fundamentals and not args.skip_fundamentals:
        print("[stocks] fundamentals + shareholding (Screener)")
        seed_fundamentals.seed(dry_run=args.dry_run, limit=args.limit)
    elif not args.skip_fundamentals:
        print("[stocks] fundamentals skipped (pass --with-fundamentals to enable)")


def _seed_funds(args, data_dir: Path) -> None:
    print("\n--- Mutual funds ---")
    if not args.skip_masters:
        print("[funds] masters")
        seed_funds.seed(data_dir=data_dir, dry_run=args.dry_run)
    if not args.skip_nav:
        print("[funds] NAV history (mftool/MFAPI)")
        seed_fund_nav.seed(dry_run=args.dry_run, limit=args.limit)


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
    parser.add_argument("--price-period", default="5y", help="yfinance period for stock prices")
    parser.add_argument("--index-period", default="max", help="yfinance period for index history")
    parser.add_argument("--batch-size", type=int, default=20, help="Stock price download batch size")
    parser.add_argument("--limit", type=int, default=None, help="Cap rows for history/NAV/fundamentals phases")
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
