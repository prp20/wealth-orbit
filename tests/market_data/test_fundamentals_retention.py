"""Fundamentals retention keeps 5 annual + 6 quarterly period ends."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.fundamentals_retention import (
    ANNUAL_KEEP,
    QUARTERLY_KEEP,
    prune_fundamental_periods,
)


class _FakeCursor:
    def __init__(self):
        self.sql = None
        self.params = None
        self.rowcount = 12

    def execute(self, sql, params=None):
        self.sql = sql
        self.params = params


def test_retention_constants():
    assert ANNUAL_KEEP == 5
    assert QUARTERLY_KEEP == 6


def test_prune_fundamental_periods_passes_caps_and_stock_id():
    cur = _FakeCursor()
    stock_id = "11111111-1111-1111-1111-111111111111"
    deleted = prune_fundamental_periods(cur, stock_id)
    assert deleted == 12
    assert "DENSE_RANK" in cur.sql
    assert cur.params == (stock_id, stock_id, ANNUAL_KEEP, QUARTERLY_KEEP)


def test_prune_fundamental_periods_allows_global_trim():
    cur = _FakeCursor()
    prune_fundamental_periods(cur, None)
    assert cur.params[0] is None
    assert cur.params[2] == ANNUAL_KEEP
    assert cur.params[3] == QUARTERLY_KEEP


def test_sync_fundamentals_calls_prune():
    src = (
        Path(__file__).resolve().parents[2]
        / "portfolio-service"
        / "backend"
        / "reference_service.py"
    ).read_text(encoding="utf-8")
    assert "prune_fundamental_periods(cur, stock_id)" in src
