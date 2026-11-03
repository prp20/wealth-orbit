"""Load non-historical stock and mutual-fund reference data into Supabase.

Canonical entrypoint is ``scripts/seed/run_all_seeds.py``. This wrapper seeds
masters only (indexes, stocks, funds) for backward compatibility.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent / "seed"
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_funds
import seed_indexes
import seed_stocks
from _db import resolve_data_dir


def main():
    parser = argparse.ArgumentParser(
        description="Seed market_data masters (indexes, stocks, mutual funds). "
        "Prefer: python portfolio-service/scripts/seed/run_all_seeds.py"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing indices.csv, stocks.csv, new_equity_only_updated.csv",
    )
    parser.add_argument(
        "--stocks",
        type=Path,
        default=None,
        help="Deprecated: path to stocks.csv (data-dir becomes its parent)",
    )
    parser.add_argument(
        "--mutual-funds",
        type=Path,
        default=None,
        help="Deprecated: path to funds CSV (ignored when --data-dir/--stocks set parent)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.data_dir is not None:
        data_dir = resolve_data_dir(args.data_dir)
    elif args.stocks is not None:
        data_dir = resolve_data_dir(args.stocks.parent)
    else:
        data_dir = resolve_data_dir(None)

    print(f"Loading reference masters from {data_dir}")
    seed_indexes.seed(data_dir=data_dir, dry_run=args.dry_run)
    seed_stocks.seed(data_dir=data_dir, dry_run=args.dry_run)
    seed_funds.seed(data_dir=data_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
