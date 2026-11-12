"""Seed latest-day technicals and Yahoo daily metrics for active stocks.

Requires OHLC rows already present (run seed_stock_prices / sync_yfinance first).
Technicals are computed from prices and stored for the latest trading day only.
"""
from __future__ import annotations

import argparse
import time

from _db import assert_database_writable, connect, ensure_project_paths

ensure_project_paths()

_TRANSIENT_TOKENS = (
    "timed out",
    "timeout",
    "already closed",
    "host not found",
    "connection refused",
    "server closed",
    "ssl connection",
    "temporary failure",
    "name or service not known",
    "could not translate host",
    "too many connections",
    "terminating connection",
)

_READ_ONLY_TOKENS = ("read-only", "database is read-only")


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


def _already_synced_metrics() -> set[str]:
    with connect() as connection:
        with connection.cursor() as cur:
            cur.execute(
                """SELECT sr.trading_symbol
                   FROM market_data.stock_reference sr
                   WHERE sr.is_active = TRUE
                     AND EXISTS (
                       SELECT 1 FROM market_data.stock_daily_metrics m
                       WHERE m.stock_id = sr.stock_id
                     )"""
            )
            return {row[0] for row in cur.fetchall()}


def _is_transient(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in _TRANSIENT_TOKENS)


def _is_read_only(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in _READ_ONLY_TOKENS)


def seed(
    dry_run: bool = False,
    limit: int | None = None,
    delay_secs: float = 0.5,
    symbols: list[str] | None = None,
    *,
    with_daily_metrics: bool = True,
    with_technicals: bool = True,
    force: bool = False,
    resume: bool = True,
    attempts: int = 4,
) -> dict:
    from _db import sanitize_seed_error

    if not with_daily_metrics and not with_technicals:
        print("  Nothing to sync — pass metrics and/or technicals.")
        return {"stocks": 0, "ok": 0, "failed": 0, "metrics_ok": 0, "technicals_ok": 0}

    symbols = _resolve_symbols(limit, symbols)
    if not symbols:
        print("  No active stocks found. Run seed_stocks.py first.")
        return {"stocks": 0, "ok": 0, "failed": 0, "metrics_ok": 0, "technicals_ok": 0}

    skipped = 0
    if resume and not force and not dry_run and with_daily_metrics and not with_technicals:
        done = _already_synced_metrics()
        if done:
            before = len(symbols)
            symbols = [symbol for symbol in symbols if symbol not in done]
            skipped = before - len(symbols)
            print(f"  Resume: skipping {skipped} symbols that already have daily metrics")

    targets = []
    if with_technicals:
        targets.append("technicals")
    if with_daily_metrics:
        targets.append("daily_metrics")
    print(
        f"  Syncing {'+'.join(targets)} for {len(symbols)} stocks"
        f"{'  [DRY RUN]' if dry_run else ''}"
    )
    if dry_run:
        for symbol in symbols[:5]:
            print(f"    {symbol}")
        return {
            "stocks": len(symbols),
            "ok": 0,
            "failed": 0,
            "skipped": skipped,
            "metrics_ok": 0,
            "technicals_ok": 0,
        }

    if not symbols:
        print("  Nothing left to sync.")
        return {
            "stocks": 0,
            "ok": 0,
            "failed": 0,
            "skipped": skipped,
            "metrics_ok": 0,
            "technicals_ok": 0,
        }

    assert_database_writable()
    from backend.market_data.sync import sync_daily_metrics, sync_technical_indicators

    ok = 0
    metrics_ok = 0
    technicals_ok = 0
    failed: list[str] = []
    for position, symbol in enumerate(symbols, 1):
        print(f"  [{position}/{len(symbols)}] {symbol}", end="", flush=True)
        succeeded = False
        details: list[str] = []
        for attempt in range(1, attempts + 1):
            try:
                if with_technicals:
                    tech = sync_technical_indicators(symbol, force=force)
                    if tech.get("status") == "completed":
                        technicals_ok += 1
                        details.append(f"tech={tech.get('trading_date')}")
                    else:
                        raise RuntimeError(tech.get("reason") or "technical sync failed")
                if with_daily_metrics:
                    result = sync_daily_metrics(symbol, force=force)
                    if result.get("status") == "completed":
                        metrics_ok += 1
                        details.append(f"metrics={result.get('metric_date')}")
                    else:
                        raise RuntimeError(result.get("reason") or "metrics sync failed")
                succeeded = True
                break
            except Exception as exc:
                detail = f"FAILED:{sanitize_seed_error(exc)}"
                if _is_read_only(exc):
                    print(f"  {detail}")
                    raise SystemExit(
                        "ERROR: database is read-only. Check the Supabase dashboard "
                        "(disk quota / pause / maintenance), free space or upgrade, "
                        "then re-run. Stopping so we do not retry every symbol."
                    ) from None
                if _is_transient(exc) and attempt < attempts:
                    wait = min(30.0, 2.0 * attempt)
                    print(
                        f"  retry {attempt}/{attempts} after {wait:.0f}s ({sanitize_seed_error(exc)})",
                        flush=True,
                    )
                    time.sleep(wait)
                    continue
                details = [detail]
                break
        if succeeded:
            ok += 1
            print(f"  {', '.join(details)}")
        else:
            failed.append(symbol)
            print(f"  {', '.join(details)}")
        time.sleep(delay_secs)

    print(
        f"  Sync complete: {ok} ok, {len(failed)} failed, {skipped} skipped "
        f"(technicals_ok={technicals_ok}, metrics_ok={metrics_ok})"
    )
    return {
        "stocks": len(symbols),
        "ok": ok,
        "failed": len(failed),
        "failed_symbols": failed,
        "skipped": skipped,
        "metrics_ok": metrics_ok,
        "technicals_ok": technicals_ok,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Seed latest-day technicals and Yahoo daily metrics for active stocks"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true", help="Recompute even when rows exist")
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Do not skip symbols that already have daily metrics (metrics-only mode)",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=4,
        help="Retries per symbol on transient DB/network errors (default 4)",
    )
    parser.add_argument(
        "--skip-daily-metrics",
        action="store_true",
        help="Skip Yahoo daily metrics sync",
    )
    parser.add_argument(
        "--skip-technicals",
        action="store_true",
        help="Skip latest-day technical indicator sync",
    )
    args = parser.parse_args()
    print("=== Seeding technicals + daily metrics ===")
    seed(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_secs=args.delay,
        force=args.force,
        resume=not args.no_resume,
        attempts=max(1, args.attempts),
        with_daily_metrics=not args.skip_daily_metrics,
        with_technicals=not args.skip_technicals,
    )
    print("Done.")


if __name__ == "__main__":
    main()
