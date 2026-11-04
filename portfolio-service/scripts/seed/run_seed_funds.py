"""Seed mutual-fund masters and NAV history only.

Does not sync metrics/enrichment/benchmark jobs — those are on-demand from the
fund detail UI (or API sync endpoints) after NAV exists.

Usage:
  uv run python portfolio-service/scripts/seed/run_seed_funds.py --data-dir data/seed
  uv run python portfolio-service/scripts/seed/run_seed_funds.py --limit 10
  uv run python portfolio-service/scripts/seed/run_seed_funds.py --skip-nav
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parent
if str(SEED_DIR) not in sys.path:
    sys.path.insert(0, str(SEED_DIR))

import seed_fund_nav
import seed_funds
from _db import resolve_data_dir


def main():
    parser = argparse.ArgumentParser(description="Seed mutual funds (masters + NAV history)")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-masters", action="store_true")
    parser.add_argument("--skip-nav", action="store_true")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    print("\n=== Seed mutual funds ===")
    print(f"data-dir: {data_dir}")

    if not args.skip_masters:
        print("\n[1] Mutual-fund masters")
        seed_funds.seed(data_dir=data_dir, dry_run=args.dry_run)
    else:
        print("\n[skipped] Mutual-fund masters")

    if not args.skip_nav:
        print("\n[2] Fund NAV history (mftool → MFAPI)")
        seed_fund_nav.seed(dry_run=args.dry_run, limit=args.limit)
    else:
        print("\n[skipped] Fund NAV")

    print(
        "\nMutual-fund seeding complete.\n"
        "Next (from UI/API as needed): Sync NAV → Benchmark → Enrichment → Metrics.\n"
        "Alpha/Beta require mapped benchmark history + Metrics sync.\n"
        "AUM / expense / manager require Enrichment sync (Kuvera + mftool).\n"
    )


if __name__ == "__main__":
    main()
