"""Cap stored statement periods: 5 annual + 6 quarterly per stock/basis."""
from __future__ import annotations

import uuid

ANNUAL_KEEP = 5
QUARTERLY_KEEP = 6


def prune_fundamental_periods(cur, stock_id: uuid.UUID | None = None) -> int:
    """Delete surplus fundamental rows. Returns deleted row count.

    Keeps the newest ``ANNUAL_KEEP`` distinct annual ``period_end_date`` values and
    ``QUARTERLY_KEEP`` distinct quarterly ends for each ``(stock_id, reporting_basis)``.
    """
    cur.execute(
        """
        DELETE FROM market_data.stock_fundamental_values AS v
        WHERE EXISTS (
          SELECT 1
          FROM (
            SELECT
              d.stock_id,
              d.reporting_basis,
              d.reporting_period,
              d.period_end_date,
              DENSE_RANK() OVER (
                PARTITION BY d.stock_id, d.reporting_basis, d.reporting_period
                ORDER BY d.period_end_date DESC
              ) AS rn
            FROM (
              SELECT DISTINCT
                stock_id,
                reporting_basis,
                reporting_period,
                period_end_date
              FROM market_data.stock_fundamental_values
              WHERE (%s::uuid IS NULL OR stock_id = %s)
            ) AS d
          ) AS ranked
          WHERE ranked.stock_id = v.stock_id
            AND ranked.reporting_basis = v.reporting_basis
            AND ranked.reporting_period = v.reporting_period
            AND ranked.period_end_date = v.period_end_date
            AND (
              (ranked.reporting_period = 'ANNUAL' AND ranked.rn > %s)
              OR (ranked.reporting_period = 'QUARTERLY' AND ranked.rn > %s)
            )
        )
        """,
        (stock_id, stock_id, ANNUAL_KEEP, QUARTERLY_KEEP),
    )
    return int(cur.rowcount or 0)


def count_surplus_fundamental_periods(cur) -> int:
    """Count rows that would be deleted by a full fundamentals prune."""
    cur.execute(
        """
        SELECT COUNT(*)
        FROM market_data.stock_fundamental_values AS v
        WHERE EXISTS (
          SELECT 1
          FROM (
            SELECT
              d.stock_id,
              d.reporting_basis,
              d.reporting_period,
              d.period_end_date,
              DENSE_RANK() OVER (
                PARTITION BY d.stock_id, d.reporting_basis, d.reporting_period
                ORDER BY d.period_end_date DESC
              ) AS rn
            FROM (
              SELECT DISTINCT
                stock_id,
                reporting_basis,
                reporting_period,
                period_end_date
              FROM market_data.stock_fundamental_values
            ) AS d
          ) AS ranked
          WHERE ranked.stock_id = v.stock_id
            AND ranked.reporting_basis = v.reporting_basis
            AND ranked.reporting_period = v.reporting_period
            AND ranked.period_end_date = v.period_end_date
            AND (
              (ranked.reporting_period = 'ANNUAL' AND ranked.rn > %s)
              OR (ranked.reporting_period = 'QUARTERLY' AND ranked.rn > %s)
            )
        )
        """,
        (ANNUAL_KEEP, QUARTERLY_KEEP),
    )
    return int(cur.fetchone()[0] or 0)
