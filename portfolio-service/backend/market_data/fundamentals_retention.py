"""Cap stored statement periods: 6 annual + 6 quarterly per stock/basis."""
from __future__ import annotations

import uuid

ANNUAL_KEEP = 6
QUARTERLY_KEEP = 6

_ANNUAL_TABLE = "market_data.stock_annual_fundamental_values"
_QUARTERLY_TABLE = "market_data.stock_quarterly_fundamental_values"


def _prune_table(cur, table: str, keep: int, stock_id: uuid.UUID | None) -> int:
    cur.execute(
        f"""
        DELETE FROM {table} AS v
        WHERE EXISTS (
          SELECT 1
          FROM (
            SELECT
              d.stock_id,
              d.reporting_basis,
              d.period_end_date,
              DENSE_RANK() OVER (
                PARTITION BY d.stock_id, d.reporting_basis
                ORDER BY d.period_end_date DESC
              ) AS rn
            FROM (
              SELECT DISTINCT
                stock_id,
                reporting_basis,
                period_end_date
              FROM {table}
              WHERE (%s::uuid IS NULL OR stock_id = %s)
            ) AS d
          ) AS ranked
          WHERE ranked.stock_id = v.stock_id
            AND ranked.reporting_basis = v.reporting_basis
            AND ranked.period_end_date = v.period_end_date
            AND ranked.rn > %s
        )
        """,
        (stock_id, stock_id, keep),
    )
    return int(cur.rowcount or 0)


def _count_surplus_table(cur, table: str, keep: int) -> int:
    cur.execute(
        f"""
        SELECT COUNT(*)
        FROM {table} AS v
        WHERE EXISTS (
          SELECT 1
          FROM (
            SELECT
              d.stock_id,
              d.reporting_basis,
              d.period_end_date,
              DENSE_RANK() OVER (
                PARTITION BY d.stock_id, d.reporting_basis
                ORDER BY d.period_end_date DESC
              ) AS rn
            FROM (
              SELECT DISTINCT
                stock_id,
                reporting_basis,
                period_end_date
              FROM {table}
            ) AS d
          ) AS ranked
          WHERE ranked.stock_id = v.stock_id
            AND ranked.reporting_basis = v.reporting_basis
            AND ranked.period_end_date = v.period_end_date
            AND ranked.rn > %s
        )
        """,
        (keep,),
    )
    return int(cur.fetchone()[0] or 0)


def prune_fundamental_periods(cur, stock_id: uuid.UUID | None = None) -> int:
    """Delete surplus fundamental rows. Returns deleted row count.

    Keeps the newest ``ANNUAL_KEEP`` distinct annual ``period_end_date`` values and
    ``QUARTERLY_KEEP`` distinct quarterly ends for each ``(stock_id, reporting_basis)``.
    """
    deleted = _prune_table(cur, _ANNUAL_TABLE, ANNUAL_KEEP, stock_id)
    deleted += _prune_table(cur, _QUARTERLY_TABLE, QUARTERLY_KEEP, stock_id)
    return deleted


def count_surplus_fundamental_periods(cur) -> int:
    """Count rows that would be deleted by a full fundamentals prune."""
    return _count_surplus_table(cur, _ANNUAL_TABLE, ANNUAL_KEEP) + _count_surplus_table(
        cur, _QUARTERLY_TABLE, QUARTERLY_KEEP
    )
