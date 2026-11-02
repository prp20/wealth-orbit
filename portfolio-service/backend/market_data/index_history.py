"""Resolve the date/value columns of the shared index history table.

Older Supabase installations used ``trading_date`` (or ``date``), while the
current migrations call the column ``history_date``.  Keeping the resolver in
one place lets workers and read APIs operate against either schema during the
rolling migration.
"""
from __future__ import annotations

DATE_COLUMNS = ("history_date", "trading_date", "date", "index_date", "price_date")
CLOSE_COLUMNS = ("close", "index_value", "value", "nav")


def quote_identifier(name: str) -> str:
    if name not in DATE_COLUMNS + CLOSE_COLUMNS:
        raise ValueError(f"Unsupported index-history column: {name}")
    return '"' + name + '"'


def resolve_index_history_columns(cur) -> tuple[str, str]:
    cur.execute(
        """SELECT column_name FROM information_schema.columns
           WHERE table_schema='market_data' AND table_name='index_daily_history'"""
    )
    columns = {row[0] for row in cur.fetchall()}
    date_column = next((name for name in DATE_COLUMNS if name in columns), None)
    close_column = next((name for name in CLOSE_COLUMNS if name in columns), None)
    if not date_column or not close_column:
        raise RuntimeError(
            "market_data.index_daily_history is missing a supported date/close column; "
            f"found {sorted(columns)}"
        )
    return date_column, close_column
