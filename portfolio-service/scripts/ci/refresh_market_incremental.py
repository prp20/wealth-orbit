#!/usr/bin/env python3
"""Incremental market_data refresh for GitHub Actions (and local dry-runs).

Refreshes only instruments that already have history in Supabase (seeded /
tracked symbols) — never full-history reloads.

Requires:
  DATABASE_URL  — session-pooler URI for a market *writer* role
                  (prefer gha_market_writer; see supabase/gha_market_writer.sql)

Must NOT be given:
  PORTFOLIO_ENCRYPTION_SECRET, SUPABASE_SERVICE_ROLE_KEY, or vault privileges

Usage:
  uv run python portfolio-service/scripts/ci/refresh_market_incremental.py
  uv run python portfolio-service/scripts/ci/refresh_market_incremental.py --dry-run
  MARKET_REFRESH_STOCK_LIMIT=20 uv run python ...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")
# portfolio-service for `backend.*`; repo root for `backend_api.*` (used by sync helpers).
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "portfolio-service"))

logger = logging.getLogger("wealth_orbit.ci.market_refresh")

# Lookback past watermark so late Yahoo revisions / holidays still upsert.
STOCK_WATERMARK_LOOKBACK_DAYS = 7
DEFAULT_STOCK_LIMIT = 50
DEFAULT_FUND_LIMIT = 30
STOCK_PAUSE_SECS = 0.35


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def require_database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is required (market writer session pooler URI)")
    return url


def assert_no_vault_secrets() -> None:
    """Refuse to run if vault/encryption secrets are present in the GHA job env.

    Local `.env` may still contain these; CI should only inject MARKET_DATABASE_URL
    as DATABASE_URL. When CI=true, treat vault secrets as a hard failure.
    """
    if (os.environ.get("CI") or "").lower() not in {"1", "true", "yes"}:
        return
    forbidden = (
        "PORTFOLIO_ENCRYPTION_SECRET",
        "SUPABASE_SERVICE_ROLE_KEY",
        "VAULT_USER_ID",
    )
    present = [name for name in forbidden if (os.environ.get(name) or "").strip()]
    if present:
        raise SystemExit(
            "Refusing to run market refresh with vault/admin secrets in CI env: "
            + ", ".join(present)
        )


def list_active_index_codes(conn) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT i.index_code
            FROM market_data.index_reference i
            JOIN market_data.index_provider_mappings m ON m.index_id = i.index_id
            WHERE i.is_active IS DISTINCT FROM FALSE
              AND m.provider = 'yfinance'
              AND m.is_active = TRUE
              AND m.trading_symbol IS NOT NULL
              AND btrim(m.trading_symbol) <> ''
            ORDER BY i.index_code
            """
        )
        return [str(row[0]) for row in cur.fetchall() if row[0]]


def list_seeded_stock_symbols(conn, *, limit: int) -> list[tuple[str, date | None]]:
    """Active stocks that already have at least one daily price row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.trading_symbol, MAX(p.trading_date) AS watermark
            FROM market_data.stock_reference s
            JOIN market_data.stock_daily_prices p ON p.stock_id = s.stock_id
            WHERE s.is_active = TRUE
            GROUP BY s.trading_symbol
            ORDER BY s.trading_symbol
            LIMIT %s
            """,
            (limit,),
        )
        return [(str(sym), wm) for sym, wm in cur.fetchall()]


def list_seeded_fund_codes(conn, *, limit: int) -> list[str]:
    """Active funds that already have NAV history."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT m.scheme_code
            FROM market_data.mutual_fund_reference m
            WHERE m.is_active = TRUE
              AND EXISTS (
                SELECT 1 FROM market_data.mutual_fund_nav_history h
                WHERE h.scheme_id = m.scheme_id
              )
            ORDER BY m.scheme_code
            LIMIT %s
            """,
            (limit,),
        )
        return [str(row[0]) for row in cur.fetchall() if row[0]]


def stock_from_date(watermark: date | None) -> date:
    if watermark is None:
        return date.today() - timedelta(days=14)
    return watermark - timedelta(days=STOCK_WATERMARK_LOOKBACK_DAYS)


def refresh_indexes(*, dry_run: bool) -> dict:
    with psycopg2.connect(require_database_url(), connect_timeout=30) as conn:
        codes = list_active_index_codes(conn)
    if not codes:
        logger.warning("no active index mappings found; skipping index refresh")
        return {"kind": "indexes", "status": "skipped", "codes": []}
    if dry_run:
        logger.info("dry-run indexes (%d): %s", len(codes), ", ".join(codes[:20]))
        return {"kind": "indexes", "status": "dry-run", "codes": codes}
    from backend.market_data.index_sync import sync_home_indexes

    # history_period=None → watermark incremental path inside sync_home_indexes
    result = sync_home_indexes(codes, history_period=None)
    logger.info(
        "indexes done synced=%s failed=%s records=%s",
        len(result.get("synced") or []),
        len(result.get("failed") or []),
        result.get("records_processed"),
    )
    return {"kind": "indexes", "status": "completed", **result}


def refresh_stocks(*, dry_run: bool, limit: int) -> dict:
    with psycopg2.connect(require_database_url(), connect_timeout=30) as conn:
        symbols = list_seeded_stock_symbols(conn, limit=limit)

    ok, failed = [], []
    if dry_run:
        logger.info("dry-run stocks (%d)", len(symbols))
        for sym, wm in symbols[:30]:
            logger.info("  %s watermark=%s from=%s", sym, wm, stock_from_date(wm))
        return {
            "kind": "stocks",
            "status": "dry-run",
            "count": len(symbols),
            "symbols": [s for s, _ in symbols],
        }

    from backend.market_data.sync import (
        sync_daily_metrics,
        sync_prices,
        sync_technical_indicators,
    )

    end = date.today() + timedelta(days=1)
    for i, (symbol, watermark) in enumerate(symbols):
        start = stock_from_date(watermark)
        try:
            price = sync_prices(symbol, force=False, from_date=start, to_date=end)
            metrics = sync_daily_metrics(symbol, force=False)
            tech = sync_technical_indicators(symbol, force=False)
            ok.append(
                {
                    "symbol": symbol,
                    "prices": price.get("records_processed"),
                    "metrics": metrics.get("status") or metrics.get("records_processed"),
                    "technicals": tech.get("status") or tech.get("records_processed"),
                }
            )
            logger.info(
                "stock %s prices=%s metrics=%s tech=%s",
                symbol,
                price.get("records_processed"),
                metrics.get("status", "ok"),
                tech.get("status", "ok"),
            )
        except Exception as exc:
            logger.exception("stock refresh failed symbol=%s", symbol)
            failed.append({"symbol": symbol, "error": str(exc)})
        if i + 1 < len(symbols):
            time.sleep(STOCK_PAUSE_SECS)

    return {
        "kind": "stocks",
        "status": "completed",
        "ok": len(ok),
        "failed": failed,
        "details": ok,
    }


def refresh_funds(*, dry_run: bool, limit: int) -> dict:
    with psycopg2.connect(require_database_url(), connect_timeout=30) as conn:
        codes = list_seeded_fund_codes(conn, limit=limit)

    if dry_run:
        logger.info("dry-run funds (%d): %s", len(codes), ", ".join(codes[:20]))
        return {"kind": "funds", "status": "dry-run", "count": len(codes), "codes": codes}

    from backend.mutual_fund_service import sync_nav

    ok, failed = [], []
    for scheme_code in codes:
        try:
            result = sync_nav(scheme_code, force=False)
            ok.append(
                {
                    "scheme_code": scheme_code,
                    "records_processed": result.get("records_processed"),
                    "up_to_date": result.get("up_to_date"),
                }
            )
            logger.info(
                "fund %s records=%s up_to_date=%s",
                scheme_code,
                result.get("records_processed"),
                result.get("up_to_date"),
            )
        except Exception as exc:
            logger.exception("fund NAV refresh failed scheme_code=%s", scheme_code)
            failed.append({"scheme_code": scheme_code, "error": str(exc)})

    return {
        "kind": "funds",
        "status": "completed",
        "ok": len(ok),
        "failed": failed,
        "details": ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Incremental market_data refresh (CI)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List targets and exit without Yahoo/MFAPI writes",
    )
    parser.add_argument(
        "--skip-stocks",
        action="store_true",
        help="Only refresh indexes (+ funds unless --skip-funds)",
    )
    parser.add_argument(
        "--skip-funds",
        action="store_true",
        help="Skip mutual-fund NAV refresh",
    )
    parser.add_argument(
        "--skip-indexes",
        action="store_true",
        help="Skip index watermark refresh",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    assert_no_vault_secrets()
    require_database_url()

    stock_limit = _env_int("MARKET_REFRESH_STOCK_LIMIT", DEFAULT_STOCK_LIMIT)
    fund_limit = _env_int("MARKET_REFRESH_FUND_LIMIT", DEFAULT_FUND_LIMIT)

    summaries: list[dict] = []
    hard_fail = False

    if not args.skip_indexes:
        try:
            summaries.append(refresh_indexes(dry_run=args.dry_run))
        except Exception:
            logger.exception("index refresh failed")
            hard_fail = True
            summaries.append({"kind": "indexes", "status": "failed"})

    if not args.skip_stocks:
        try:
            stock_summary = refresh_stocks(dry_run=args.dry_run, limit=stock_limit)
            summaries.append(stock_summary)
            if (
                not args.dry_run
                and stock_summary.get("ok", 0) == 0
                and stock_summary.get("failed")
            ):
                hard_fail = True
        except Exception:
            logger.exception("stock refresh failed")
            hard_fail = True
            summaries.append({"kind": "stocks", "status": "failed"})

    if not args.skip_funds:
        try:
            fund_summary = refresh_funds(dry_run=args.dry_run, limit=fund_limit)
            summaries.append(fund_summary)
        except Exception:
            logger.exception("fund refresh failed")
            # Funds are best-effort; do not fail the whole job unless nothing else ran.
            summaries.append({"kind": "funds", "status": "failed"})

    for item in summaries:
        logger.info("summary %s", item)

    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
