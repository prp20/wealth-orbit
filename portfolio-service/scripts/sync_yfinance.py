"""Sync daily OHLCV history for Supabase stock references via yfinance.

Canonical entrypoint is ``scripts/seed/seed_stock_prices.py`` (also run via
``scripts/seed/run_all_seeds.py``). This wrapper delegates to the batched seeder.
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message=".*inplace keyword.*", category=Warning)

SEED_DIR = Path(__file__).resolve().parent / "seed"
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_stock_prices


def main():
    parser = argparse.ArgumentParser(
        description="Sync stock_daily_prices via yfinance (delegates to seed_stock_prices)"
    )
    parser.add_argument(
        "--period",
        default="10y",
        help="yfinance period (default 10y; use max only as an explicit opt-in)",
    )
    parser.add_argument("--source-name", default="yfinance", help="Ignored; source is always yfinance")
    parser.add_argument("--force", action="store_true", help="Ignored; upserts always refresh conflicting dates")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    _ = args.source_name, args.force  # retained for CLI compatibility
    seed_stock_prices.seed(
        period=args.period,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        limit=args.limit,
        data_dir=args.data_dir,
    )


if __name__ == "__main__":
    main()
