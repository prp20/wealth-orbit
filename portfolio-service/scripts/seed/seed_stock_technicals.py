"""Seed latest-day technicals and Yahoo daily metrics for active stocks.

Requires OHLC rows already present (run seed_stock_prices / sync_yfinance first).
Technicals are computed from prices and stored for the latest trading day only.
"""
from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
DEFAULT_WORKERS = 8


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


def _sync_symbol(
    symbol: str,
    *,
    with_technicals: bool,
    with_daily_metrics: bool,
    force: bool,
    attempts: int,
    delay_secs: float,
) -> dict:
    from _db import sanitize_seed_error
    from backend.market_data.sync import sync_daily_metrics, sync_technical_indicators

    details: list[str] = []
    technicals_ok = 0
    metrics_ok = 0
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            if with_technicals:
                tech = sync_technical_indicators(symbol, force=force)
                if tech.get("status") != "completed":
                    raise RuntimeError(tech.get("reason") or "technical sync failed")
                technicals_ok = 1
                details.append(f"tech={tech.get('trading_date')}")
            if with_daily_metrics:
                result = sync_daily_metrics(symbol, force=force)
                if result.get("status") != "completed":
                    raise RuntimeError(result.get("reason") or "metrics sync failed")
                metrics_ok = 1
                details.append(f"metrics={result.get('metric_date')}")
            if delay_secs > 0:
                time.sleep(delay_secs)
            return {
                "symbol": symbol,
                "ok": True,
                "details": details,
                "technicals_ok": technicals_ok,
                "metrics_ok": metrics_ok,
            }
        except Exception as exc:
            last_error = sanitize_seed_error(exc)
            if _is_read_only(exc):
                return {
                    "symbol": symbol,
                    "ok": False,
                    "read_only": True,
                    "details": [f"FAILED:{last_error}"],
                    "technicals_ok": 0,
                    "metrics_ok": 0,
                }
            if _is_transient(exc) and attempt < attempts:
                time.sleep(min(30.0, 2.0 * attempt))
                continue
            break
    return {
        "symbol": symbol,
        "ok": False,
        "read_only": False,
        "details": [f"FAILED:{last_error}"],
        "technicals_ok": 0,
        "metrics_ok": 0,
    }


def seed(
    dry_run: bool = False,
    limit: int | None = None,
    delay_secs: float = 0.0,
    symbols: list[str] | None = None,
    *,
    with_daily_metrics: bool = True,
    with_technicals: bool = True,
    force: bool = False,
    resume: bool = True,
    attempts: int = 4,
    workers: int = DEFAULT_WORKERS,
) -> dict:
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

    workers = max(1, int(workers or 1))
    # Yahoo metrics rate-limit: keep a tiny per-worker pause unless caller set delay.
    if delay_secs is None:
        delay_secs = 0.0
    if delay_secs <= 0 and with_daily_metrics and workers > 1:
        delay_secs = 0.05

    targets = []
    if with_technicals:
        targets.append("technicals")
    if with_daily_metrics:
        targets.append("daily_metrics")
    print(
        f"  Syncing {'+'.join(targets)} for {len(symbols)} stocks "
        f"(workers={workers})"
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
            "workers": workers,
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
            "workers": workers,
        }

    assert_database_writable()

    ok = 0
    metrics_ok = 0
    technicals_ok = 0
    failed: list[str] = []
    completed = 0
    total = len(symbols)
    print_lock = threading.Lock()
    stop = threading.Event()

    def _run(symbol: str) -> dict:
        if stop.is_set():
            return {
                "symbol": symbol,
                "ok": False,
                "skipped_stop": True,
                "details": ["FAILED:stopped"],
                "technicals_ok": 0,
                "metrics_ok": 0,
            }
        return _sync_symbol(
            symbol,
            with_technicals=with_technicals,
            with_daily_metrics=with_daily_metrics,
            force=force,
            attempts=attempts,
            delay_secs=delay_secs,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run, symbol): symbol for symbol in symbols}
        for future in as_completed(futures):
            result = future.result()
            if result.get("read_only"):
                stop.set()
                with print_lock:
                    print(f"  [{result['symbol']}]  {', '.join(result['details'])}", flush=True)
                raise SystemExit(
                    "ERROR: database is read-only. Check the Supabase dashboard "
                    "(disk quota / pause / maintenance), free space or upgrade, "
                    "then re-run. Stopping so we do not retry every symbol."
                )
            if result.get("skipped_stop"):
                continue
            completed += 1
            if result["ok"]:
                ok += 1
                technicals_ok += int(result.get("technicals_ok") or 0)
                metrics_ok += int(result.get("metrics_ok") or 0)
            else:
                failed.append(result["symbol"])
            with print_lock:
                print(
                    f"  [{completed}/{total}] {result['symbol']}  {', '.join(result['details'])}",
                    flush=True,
                )

    print(
        f"  Sync complete: {ok} ok, {len(failed)} failed, {skipped} skipped "
        f"(technicals_ok={technicals_ok}, metrics_ok={metrics_ok}, workers={workers})"
    )
    return {
        "stocks": len(symbols),
        "ok": ok,
        "failed": len(failed),
        "failed_symbols": failed,
        "skipped": skipped,
        "metrics_ok": metrics_ok,
        "technicals_ok": technicals_ok,
        "workers": workers,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Seed latest-day technicals and Yahoo daily metrics for active stocks"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Per-worker pause after each symbol (default 0; 0.05 used automatically with Yahoo metrics)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Parallel workers (default {DEFAULT_WORKERS})",
    )
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
        workers=max(1, args.workers),
        with_daily_metrics=not args.skip_daily_metrics,
        with_technicals=not args.skip_technicals,
    )
    print("Done.")


if __name__ == "__main__":
    main()
