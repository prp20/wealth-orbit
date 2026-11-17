"""Latest-only retention for per-stock technical and daily-metrics snapshots."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Any


def prune_non_latest_technical_dates(cur, stock_id: uuid.UUID, keep_trading_date: date) -> int:
    """Drop indicator rows for any trading_date other than the current snapshot date."""
    cur.execute(
        """DELETE FROM market_data.stock_technical_indicators
           WHERE stock_id=%s AND trading_date <> %s""",
        (stock_id, keep_trading_date),
    )
    return int(getattr(cur, "rowcount", 0) or 0)


def prune_non_latest_metric_dates(cur, stock_id: uuid.UUID, keep_metric_date: Any) -> int:
    """Drop daily_metrics rows for any metric_date other than the current snapshot date."""
    cur.execute(
        """DELETE FROM market_data.stock_daily_metrics
           WHERE stock_id=%s AND metric_date <> %s""",
        (stock_id, keep_metric_date),
    )
    return int(getattr(cur, "rowcount", 0) or 0)
