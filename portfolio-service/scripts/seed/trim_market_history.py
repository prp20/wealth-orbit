"""Trim market_data retention to product defaults (10y OHLC/NAV/index).

Also prunes non-latest daily metrics, surplus fundamentals (5 annual / 6 quarterly),
and non-latest technical indicator rows. Requires a writable DATABASE_URL.
"""
from __future__ import annotations

import argparse

from _db import assert_database_writable, connect, ensure_project_paths

ensure_project_paths()

DEFAULT_YEARS = 10


def trim(*, years: int = DEFAULT_YEARS, dry_run: bool = False, vacuum: bool = False) -> dict:
    from backend.market_data.fundamentals_retention import (
        count_surplus_fundamental_periods,
        prune_fundamental_periods,
    )
    from backend.market_data.history_period import retention_cutoff
    from backend.market_data.index_history import quote_identifier, resolve_index_history_columns

    period = f"{max(1, years)}y" if years in (1, 2, 3, 5, 10) else None
    if period is not None:
        cutoff = retention_cutoff(period)
    else:
        from datetime import date, timedelta

        cutoff = date.today() - timedelta(days=365 * max(1, years))
    print(f"=== Trim market history (keep >= {cutoff}, years={years}) ===")
    if not dry_run:
        assert_database_writable()

    with connect() as connection:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM market_data.stock_daily_prices WHERE trading_date < %s",
                (cutoff,),
            )
            old_prices = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM information_schema.tables
                   WHERE table_schema='market_data'
                     AND table_name='stock_technical_indicators'"""
            )
            has_technicals = cur.fetchone()[0] > 0
            old_technicals = 0
            if has_technicals:
                cur.execute(
                    """SELECT COUNT(*) FROM market_data.stock_technical_indicators t
                       WHERE EXISTS (
                         SELECT 1 FROM market_data.stock_technical_indicators newer
                         WHERE newer.stock_id = t.stock_id
                           AND newer.trading_date > t.trading_date
                       )"""
                )
                old_technicals = cur.fetchone()[0]
            cur.execute(
                """SELECT COUNT(*) FROM market_data.stock_daily_metrics m
                   WHERE EXISTS (
                     SELECT 1 FROM market_data.stock_daily_metrics newer
                     WHERE newer.stock_id = m.stock_id
                       AND newer.metric_date > m.metric_date
                   )"""
            )
            old_metrics = cur.fetchone()[0]
            index_date_col, _close_col = resolve_index_history_columns(cur)
            cur.execute(
                f"SELECT COUNT(*) FROM market_data.index_daily_history "
                f"WHERE {quote_identifier(index_date_col)} < %s",
                (cutoff,),
            )
            old_index = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM market_data.mutual_fund_nav_history WHERE nav_date < %s",
                (cutoff,),
            )
            old_nav = cur.fetchone()[0]
            old_fundamentals = count_surplus_fundamental_periods(cur)

            print(f"  stock_daily_prices older than cutoff: {old_prices:,}")
            print(f"  stock_technical_indicators non-latest rows: {old_technicals:,}")
            print(f"  stock_daily_metrics non-latest rows: {old_metrics:,}")
            print(f"  stock_fundamental_values surplus periods: {old_fundamentals:,}")
            print(f"  index_daily_history older than cutoff: {old_index:,}")
            print(f"  mutual_fund_nav_history older than cutoff: {old_nav:,}")

            if dry_run:
                print("  [DRY RUN] no deletes performed")
                return {
                    "cutoff": str(cutoff),
                    "old_prices": old_prices,
                    "old_technicals": old_technicals,
                    "old_metrics": old_metrics,
                    "old_fundamentals": old_fundamentals,
                    "old_index": old_index,
                    "old_nav": old_nav,
                    "deleted": False,
                }

            if old_prices:
                print("  Deleting old stock_daily_prices…", flush=True)
                cur.execute(
                    "DELETE FROM market_data.stock_daily_prices WHERE trading_date < %s",
                    (cutoff,),
                )
            if has_technicals and old_technicals:
                print("  Pruning non-latest stock_technical_indicators…", flush=True)
                cur.execute(
                    """DELETE FROM market_data.stock_technical_indicators t
                       WHERE EXISTS (
                         SELECT 1 FROM market_data.stock_technical_indicators newer
                         WHERE newer.stock_id = t.stock_id
                           AND newer.trading_date > t.trading_date
                       )"""
                )
            if old_metrics:
                print("  Pruning non-latest stock_daily_metrics…", flush=True)
                cur.execute(
                    """DELETE FROM market_data.stock_daily_metrics m
                       WHERE EXISTS (
                         SELECT 1 FROM market_data.stock_daily_metrics newer
                         WHERE newer.stock_id = m.stock_id
                           AND newer.metric_date > m.metric_date
                       )"""
                )
            if old_fundamentals:
                print("  Pruning surplus fundamental periods (5 annual / 6 quarterly)…", flush=True)
                prune_fundamental_periods(cur, None)
            if old_index:
                print("  Deleting old index_daily_history…", flush=True)
                cur.execute(
                    f"DELETE FROM market_data.index_daily_history "
                    f"WHERE {quote_identifier(index_date_col)} < %s",
                    (cutoff,),
                )
            if old_nav:
                print("  Deleting old mutual_fund_nav_history…", flush=True)
                cur.execute(
                    "DELETE FROM market_data.mutual_fund_nav_history WHERE nav_date < %s",
                    (cutoff,),
                )
            connection.commit()

            size = None
            cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            size = cur.fetchone()[0]
            print(f"  Database size now: {size}")

            if vacuum:
                print("  Running VACUUM (may be restricted on hosted Postgres)…", flush=True)
                old_autocommit = connection.autocommit
                try:
                    connection.autocommit = True
                    with connection.cursor() as vac:
                        vac.execute("VACUUM")
                    print("  VACUUM completed")
                except Exception as exc:
                    print(f"  VACUUM skipped: {exc}")
                finally:
                    connection.autocommit = old_autocommit

            return {
                "cutoff": str(cutoff),
                "old_prices": old_prices,
                "old_technicals": old_technicals,
                "old_metrics": old_metrics,
                "old_fundamentals": old_fundamentals,
                "old_index": old_index,
                "old_nav": old_nav,
                "deleted": True,
                "db_size": size,
            }


def main():
    parser = argparse.ArgumentParser(description="Trim market_data history to retention policy")
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Attempt VACUUM after deletes (often blocked on Supabase pooler)",
    )
    args = parser.parse_args()
    trim(years=args.years, dry_run=args.dry_run, vacuum=args.vacuum)
    print("Done.")


if __name__ == "__main__":
    main()
