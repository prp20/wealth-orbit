"""Seed stock fundamentals and shareholding via Screener sync."""
from __future__ import annotations

import argparse
import time

from _db import assert_database_writable, connect, ensure_project_paths

ensure_project_paths()


def seed(
    dry_run: bool = False,
    limit: int | None = None,
    delay_secs: float = 3.0,
    symbols: list[str] | None = None,
) -> dict:
    from _db import normalize_limit, sanitize_seed_error

    limit = normalize_limit(limit)
    if symbols is None:
        with connect() as connection:
            with connection.cursor() as cur:
                cur.execute(
                    """SELECT trading_symbol
                       FROM market_data.stock_reference
                       WHERE is_active = TRUE
                       ORDER BY trading_symbol"""
                )
                symbols = [row[0] for row in cur.fetchall()]
        if limit is not None:
            symbols = symbols[:limit]
    else:
        symbols = [str(symbol).strip() for symbol in symbols if str(symbol).strip()]
    if not symbols:
        print("  No active stocks found. Run seed_stocks.py first.")
        return {"stocks": 0, "ok": 0, "failed": 0}

    print(f"  Syncing Screener fundamentals for {len(symbols)} stocks{'  [DRY RUN]' if dry_run else ''}")
    if dry_run:
        for symbol in symbols[:5]:
            print(f"    {symbol}")
        return {"stocks": len(symbols), "ok": 0, "failed": 0}

    assert_database_writable()
    from backend.reference_service import sync_stock_fundamentals

    ok = 0
    failed = []
    for position, symbol in enumerate(symbols, 1):
        print(f"  [{position}/{len(symbols)}] {symbol}", end="", flush=True)
        try:
            result = sync_stock_fundamentals(symbol, force=False)
            if result.get("status") == "completed":
                ok += 1
                print(
                    f"  fundamentals={result.get('fundamental_rows', 0)} "
                    f"shareholding={result.get('shareholding_rows', 0)}"
                )
            else:
                failed.append(symbol)
                print(f"  FAILED: {result.get('reason') or 'sync failed'}")
        except Exception as exc:
            reason = sanitize_seed_error(exc)
            print(f"  FAILED: {reason}")
            if "read-only" in reason.lower():
                raise SystemExit(
                    "ERROR: database is read-only. Fix Supabase disk quota / project status, "
                    "then re-run. Stopping so we do not retry every symbol."
                ) from None
            failed.append(symbol)
        time.sleep(delay_secs)

    print(f"  Fundamentals sync complete: {ok} ok, {len(failed)} failed")
    return {"stocks": len(symbols), "ok": ok, "failed": len(failed), "failed_symbols": failed}


def main():
    parser = argparse.ArgumentParser(description="Seed stock fundamentals from Screener")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args()
    print("=== Seeding fundamentals ===")
    seed(dry_run=args.dry_run, limit=args.limit, delay_secs=args.delay)
    print("Done.")


if __name__ == "__main__":
    main()
