"""Seed stock masters and market data.

By default this seeds masters + OHLC prices only. Screener fundamentals /
shareholding and derived technicals / daily metrics are optional.

Usage:
  # masters + OHLC only (default)
  uv run python portfolio-service/scripts/seed/run_seed_stocks.py --data-dir data/seed --limit 10

  # also sync Screener fundamentals + shareholding
  uv run python portfolio-service/scripts/seed/run_seed_stocks.py --with-fundamentals --limit 5

  # fundamentals only (assumes masters already loaded)
  uv run python portfolio-service/scripts/seed/run_seed_stocks.py --skip-masters --skip-prices --with-fundamentals

  # technicals + daily metrics only (assumes OHLC already loaded)
  uv run python portfolio-service/scripts/seed/run_seed_stocks.py --skip-masters --skip-prices --with-technicals
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_fundamentals
import seed_stock_prices
import seed_stock_technicals
import seed_stocks
from _db import resolve_data_dir


def main():
    parser = argparse.ArgumentParser(
        description="Seed stocks separately (masters, OHLC, optional fundamentals/technicals)"
    )
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--price-period", default="5y")
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-masters", action="store_true")
    parser.add_argument("--skip-prices", action="store_true", help="Skip Yahoo OHLC price history")
    parser.add_argument(
        "--with-fundamentals",
        action="store_true",
        help="Also sync Screener fundamentals + shareholding (off by default)",
    )
    parser.add_argument(
        "--fundamentals-only",
        action="store_true",
        help="Shortcut: skip masters/prices and only run Screener fundamentals",
    )
    parser.add_argument(
        "--with-technicals",
        action="store_true",
        help="Also sync technical indicators + Yahoo daily metrics (off by default)",
    )
    parser.add_argument(
        "--technicals-only",
        action="store_true",
        help="Shortcut: skip masters/prices/fundamentals and only run technicals + daily metrics",
    )
    parser.add_argument(
        "--fundamentals-delay",
        type=float,
        default=3.0,
        help="Seconds between Screener fundamentals calls (default 3.0)",
    )
    parser.add_argument(
        "--technicals-delay",
        type=float,
        default=0.5,
        help="Seconds between technicals/metrics symbols (default 0.5)",
    )
    args = parser.parse_args()

    if args.fundamentals_only:
        args.skip_masters = True
        args.skip_prices = True
        args.with_fundamentals = True
    if args.technicals_only:
        args.skip_masters = True
        args.skip_prices = True
        args.with_technicals = True

    data_dir = resolve_data_dir(args.data_dir)
    print("\n=== Seed stocks ===")
    print(f"data-dir: {data_dir}")
    print(
        "mode: "
        f"masters={'on' if not args.skip_masters else 'off'}, "
        f"ohlc={'on' if not args.skip_prices else 'off'}, "
        f"fundamentals={'on' if args.with_fundamentals else 'off'}, "
        f"technicals={'on' if args.with_technicals else 'off'}"
    )

    master_symbols: list[str] | None = None
    if not args.skip_masters:
        print("\n[1] Stock masters")
        # --limit caps masters too (not only OHLC), so guided setup stays small.
        masters = seed_stocks.seed(data_dir=data_dir, dry_run=args.dry_run, limit=args.limit)
        master_symbols = list(masters.get("symbols") or [])
    else:
        print("\n[skipped] Stock masters")

    if not args.skip_prices:
        print("\n[2] Stock OHLC prices (Yahoo Finance)")
        # When masters ran with --limit, reuse that CSV-order symbol set for history.
        seed_stock_prices.seed(
            period=args.price_period,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            limit=None if master_symbols is not None else args.limit,
            data_dir=data_dir,
            symbols=master_symbols,
        )
    else:
        print("\n[skipped] Stock OHLC prices")

    if args.with_fundamentals:
        print("\n[3] Stock fundamentals + shareholding (Screener)")
        seed_fundamentals.seed(
            dry_run=args.dry_run,
            limit=None if master_symbols is not None else args.limit,
            delay_secs=args.fundamentals_delay,
            symbols=master_symbols,
        )
    else:
        print("\n[skipped] Fundamentals — pass --with-fundamentals if needed")

    if args.with_technicals:
        print("\n[4] Stock technicals + daily metrics")
        seed_stock_technicals.seed(
            dry_run=args.dry_run,
            limit=None if master_symbols is not None else args.limit,
            delay_secs=args.technicals_delay,
            symbols=master_symbols,
        )
    else:
        print("\n[skipped] Technicals — pass --with-technicals if needed")

    print("\nStocks seeding complete.\n")


if __name__ == "__main__":
    main()
