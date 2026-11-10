"""Seed technical indicators and Yahoo daily metrics for active stocks.

Requires OHLC rows already present (run seed_stock_prices / sync_yfinance first).
Technicals are derived from stored prices; daily metrics hit Yahoo `.info` per symbol.
"""
from __future__ import annotations

import argparse
import time

from _db import connect, ensure_project_paths

ensure_project_paths()


def _resolve_symbols(limit: int | None, symbols: list[str] | None) -> list[str]:
    from _db import normalize_limit

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
        if limit is not None:
            symbols = symbols[:limit]
    return symbols


def seed(
    dry_run: bool = False,
    limit: int | None = None,
    delay_secs: float = 0.5,
    symbols: list[str] | None = None,
    *,
    with_technicals: bool = True,
    with_daily_metrics: bool = True,
    force: bool = False,
) -> dict:
    from _db import sanitize_seed_error

    if not with_technicals and not with_daily_metrics:
        print("  Nothing to sync — enable technicals and/or daily metrics.")
        return {"stocks": 0, "ok": 0, "failed": 0, "technical_ok": 0, "metrics_ok": 0}

    symbols = _resolve_symbols(limit, symbols)
    if not symbols:
        print("  No active stocks found. Run seed_stocks.py first.")
        return {"stocks": 0, "ok": 0, "failed": 0, "technical_ok": 0, "metrics_ok": 0}

    parts = []
    if with_technicals:
        parts.append("technicals")
    if with_daily_metrics:
        parts.append("daily_metrics")
    print(
        f"  Syncing {' + '.join(parts)} for {len(symbols)} stocks"
        f"{'  [DRY RUN]' if dry_run else ''}"
    )
    if dry_run:
        for symbol in symbols[:5]:
            print(f"    {symbol}")
        return {
            "stocks": len(symbols),
            "ok": 0,
            "failed": 0,
            "technical_ok": 0,
            "metrics_ok": 0,
        }

    from backend.market_data.sync import sync_daily_metrics, sync_technical_indicators

    ok = 0
    technical_ok = 0
    metrics_ok = 0
    failed: list[str] = []
    for position, symbol in enumerate(symbols, 1):
        print(f"  [{position}/{len(symbols)}] {symbol}", end="", flush=True)
        symbol_failed = False
        detail_parts: list[str] = []
        try:
            if with_technicals:
                result = sync_technical_indicators(symbol, force=force)
                if result.get("status") == "completed":
                    technical_ok += 1
                    detail_parts.append(f"technical={result.get('records_processed', 0)}")
                else:
                    symbol_failed = True
                    detail_parts.append(f"technical=FAILED:{result.get('reason') or 'sync failed'}")
            if with_daily_metrics:
                result = sync_daily_metrics(symbol, force=force)
                if result.get("status") == "completed":
                    metrics_ok += 1
                    detail_parts.append(f"metrics={result.get('metric_date')}")
                else:
                    symbol_failed = True
                    detail_parts.append(f"metrics=FAILED:{result.get('reason') or 'sync failed'}")
        except Exception as exc:
            symbol_failed = True
            detail_parts.append(f"FAILED:{sanitize_seed_error(exc)}")
        if symbol_failed:
            failed.append(symbol)
            print("  " + " ".join(detail_parts))
        else:
            ok += 1
            print("  " + " ".join(detail_parts))
        time.sleep(delay_secs)

    print(
        f"  Technicals/metrics sync complete: {ok} ok, {len(failed)} failed "
        f"(technical_ok={technical_ok}, metrics_ok={metrics_ok})"
    )
    return {
        "stocks": len(symbols),
        "ok": ok,
        "failed": len(failed),
        "failed_symbols": failed,
        "technical_ok": technical_ok,
        "metrics_ok": metrics_ok,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Seed technical indicators and/or Yahoo daily metrics for active stocks"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true", help="Rebuild technical rows for each symbol")
    parser.add_argument(
        "--skip-technicals",
        action="store_true",
        help="Only sync Yahoo daily metrics",
    )
    parser.add_argument(
        "--skip-daily-metrics",
        action="store_true",
        help="Only sync derived technical indicators",
    )
    args = parser.parse_args()
    print("=== Seeding technicals / daily metrics ===")
    seed(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_secs=args.delay,
        force=args.force,
        with_technicals=not args.skip_technicals,
        with_daily_metrics=not args.skip_daily_metrics,
    )
    print("Done.")


if __name__ == "__main__":
    main()
