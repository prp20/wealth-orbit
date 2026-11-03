"""Seed mutual_fund_nav_history via existing sync_nav service."""
from __future__ import annotations

import argparse
import time

from _db import connect, ensure_project_paths

ensure_project_paths()


def seed(dry_run: bool = False, limit: int | None = None, delay_secs: float = 0.5) -> dict:
    with connect() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """SELECT scheme_code, scheme_name
                   FROM market_data.mutual_fund_reference
                   WHERE scheme_code IS NOT NULL AND scheme_code <> ''
                   ORDER BY scheme_code"""
            )
            schemes = cur.fetchall()
    if limit is not None:
        schemes = schemes[:limit]
    if not schemes:
        print("  No mutual-fund schemes found. Run seed_funds.py first.")
        return {"schemes": 0, "ok": 0, "failed": 0}

    print(f"  Syncing NAV for {len(schemes)} schemes{'  [DRY RUN]' if dry_run else ''}")
    if dry_run:
        for scheme_code, scheme_name in schemes[:5]:
            print(f"    {scheme_code} | {scheme_name[:60]}")
        return {"schemes": len(schemes), "ok": 0, "failed": 0}

    from backend.mutual_fund_service import sync_nav

    ok = 0
    failed = []
    for position, (scheme_code, scheme_name) in enumerate(schemes, 1):
        print(f"  [{position}/{len(schemes)}] {scheme_code}", end="", flush=True)
        try:
            result = sync_nav(scheme_code, force=False)
            ok += 1
            print(f"  rows={result.get('records_processed', 0)}")
        except Exception as exc:
            failed.append(scheme_code)
            print(f"  FAILED: {exc}")
        time.sleep(delay_secs)

    print(f"  NAV sync complete: {ok} ok, {len(failed)} failed")
    return {"schemes": len(schemes), "ok": ok, "failed": len(failed), "failed_codes": failed}


def main():
    parser = argparse.ArgumentParser(description="Seed mutual_fund_nav_history")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    args = parser.parse_args()
    print("=== Seeding fund NAV ===")
    seed(dry_run=args.dry_run, limit=args.limit, delay_secs=args.delay)
    print("Done.")


if __name__ == "__main__":
    main()
