"""Seed index masters and (optionally) index OHLC history only.

Usage:
  uv run python portfolio-service/scripts/seed/run_seed_indexes.py --data-dir data/seed
  uv run python portfolio-service/scripts/seed/run_seed_indexes.py --skip-history
  uv run python portfolio-service/scripts/seed/run_seed_indexes.py --limit 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_index_history
import seed_indexes
from _db import resolve_data_dir


def main():
    parser = argparse.ArgumentParser(description="Seed indexes (masters + optional Yahoo history)")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--index-period", default="max")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-masters", action="store_true")
    parser.add_argument("--skip-history", action="store_true")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    print("\n=== Seed indexes ===")
    print(f"data-dir: {data_dir}")

    if not args.skip_masters:
        print("\n[1] Index masters")
        seed_indexes.seed(data_dir=data_dir, dry_run=args.dry_run)
    else:
        print("\n[skipped] Index masters")

    if not args.skip_history:
        print("\n[2] Index history (Yahoo Finance OHLC)")
        seed_index_history.seed(period=args.index_period, dry_run=args.dry_run, limit=args.limit)
    else:
        print("\n[skipped] Index history")

    print("\nIndexes seeding complete.\n")


if __name__ == "__main__":
    main()
