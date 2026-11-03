"""
run_all_seeds.py — Run Wealth Orbit market-data seed scripts in dependency order.

Order:
  1. seed_indexes        (index_reference + yfinance mappings)
  2. seed_stocks         (stock_reference)
  3. seed_funds          (mutual_fund_reference)
  4. seed_index_history  (index_daily_history via Yahoo)
  5. seed_stock_prices   (stock_daily_prices via Yahoo)
  6. seed_fund_nav       (mutual_fund_nav_history via mftool/MFAPI)
  7. seed_fundamentals  (Screener fundamentals + shareholding)

Prerequisites:
  - Alembic migrations applied; base market_data tables present in Postgres
  - DATABASE_URL set (Supabase pooler URL)
  - Seed CSVs under data/seed/ (or pass --data-dir)

Usage:
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --data-dir data/seed --dry-run
  uv run python portfolio-service/scripts/seed/run_all_seeds.py --limit 3 --skip-fundamentals
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


def main():
    parser = argparse.ArgumentParser(description="Run full-stack market-data seed scripts")
    parser.add_argument("--data-dir", type=Path, default=None, help="Directory with seed CSVs")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--price-period", default="5y", help="yfinance period for stock prices")
    parser.add_argument("--index-period", default="max", help="yfinance period for index history")
    parser.add_argument("--batch-size", type=int, default=20, help="Stock price download batch size")
    parser.add_argument("--limit", type=int, default=None, help="Cap rows for history/NAV/fundamentals phases")
    parser.add_argument("--skip-masters", action="store_true")
    parser.add_argument("--skip-index-history", action="store_true")
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-nav", action="store_true")
    parser.add_argument("--skip-fundamentals", action="store_true")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    print("\n" + "=" * 50)
    print("Wealth Orbit — Market Data Seeding")
    print(f"data-dir: {data_dir}")
    print("=" * 50)

    step = 0
    total = 7

    if not args.skip_masters:
        step += 1
        print(f"\n[{step}/{total}] Indexes (master)")
        seed_indexes.seed(data_dir=data_dir, dry_run=args.dry_run)

        step += 1
        print(f"\n[{step}/{total}] Stocks")
        seed_stocks.seed(data_dir=data_dir, dry_run=args.dry_run)

        step += 1
        print(f"\n[{step}/{total}] Mutual Funds")
        seed_funds.seed(data_dir=data_dir, dry_run=args.dry_run)
    else:
        print("\n[skipped] Masters")

    if not args.skip_index_history:
        step += 1
        print(f"\n[{step}/{total}] Index history (Yahoo Finance)")
        seed_index_history.seed(period=args.index_period, dry_run=args.dry_run, limit=args.limit)
    else:
        print("\n[skipped] Index history")

    if not args.skip_prices:
        step += 1
        print(f"\n[{step}/{total}] Stock prices (Yahoo Finance)")
        seed_stock_prices.seed(
            period=args.price_period,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=args.limit,
            data_dir=data_dir,
        )
    else:
        print("\n[skipped] Stock prices")

    if not args.skip_nav:
        step += 1
        print(f"\n[{step}/{total}] Fund NAV (mftool/MFAPI)")
        seed_fund_nav.seed(dry_run=args.dry_run, limit=args.limit)
    else:
        print("\n[skipped] Fund NAV")

    if not args.skip_fundamentals:
        step += 1
        print(f"\n[{step}/{total}] Fundamentals (Screener)")
        seed_fundamentals.seed(dry_run=args.dry_run, limit=args.limit)
    else:
        print("\n[skipped] Fundamentals")

    print("\n" + "=" * 50)
    if args.dry_run:
        print("DRY RUN complete — no data written.")
    else:
        print("Seeding complete.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
