"""calc_v1 fundamental ratios + latest-only snapshot persistence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.fundamental_ratios import (
    CALC_VERSION,
    build_latest_snapshot,
    calc_v1_from_period,
    growth_series,
    merge_top_ratios_fallback,
    period_growth,
    upsert_latest_fundamental_ratios,
)


def test_calc_v1_profitability_leverage_efficiency():
    period = {
        "REVENUE": 100.0,
        "NET_PROFIT": 20.0,
        "OPERATING_PROFIT": 30.0,
        "INTEREST_EXPENSE": 5.0,
        "EQUITY_CAPITAL": 10.0,
        "RESERVES": 40.0,
        "BORROWINGS": 25.0,
        "TOTAL_ASSETS": 200.0,
        "EPS": 2.0,
    }
    prior = {"REVENUE": 80.0, "EPS": 1.0}
    ratios = calc_v1_from_period(period, prior=prior)
    assert ratios["PAT_MARGIN"] == 20.0
    assert ratios["ROE"] == 40.0  # 20 / 50
    assert ratios["ROCE"] == 40.0  # 30 / 75
    assert ratios["DEBT_TO_EQUITY"] == 0.5
    assert ratios["INTEREST_COVERAGE"] == 6.0
    assert ratios["ASSET_TURNOVER"] == 0.5
    assert ratios["ROA"] == 10.0
    assert ratios["REVENUE_GROWTH"] == 25.0
    assert ratios["EPS_GROWTH"] == 100.0
    assert ratios["CURRENT_RATIO"] is None


def test_top_ratios_fallback_fills_gaps_only():
    computed = {"ROE": 12.0, "CURRENT_RATIO": None, "DEBT_TO_EQUITY": None}
    merged = merge_top_ratios_fallback(
        computed,
        {"ROE": "99%", "Current Ratio": "1.5", "Debt to equity": "0.8"},
    )
    assert merged["ROE"] == 12.0  # computed wins
    assert merged["CURRENT_RATIO"] == 1.5
    assert merged["DEBT_TO_EQUITY"] == 0.8


def test_period_growth_null_safe():
    assert period_growth(None, 10) is None
    assert period_growth(10, 0) is None
    assert period_growth(12, 10) == 20.0


def test_growth_series_from_statements():
    rows = [
        {"period_end_date": "2022-03-31", "metric_code": "REVENUE", "metric_value": 100},
        {"period_end_date": "2023-03-31", "metric_code": "REVENUE", "metric_value": 120},
        {"period_end_date": "2024-03-31", "metric_code": "REVENUE", "metric_value": 150},
    ]
    series = growth_series(rows, "REVENUE")
    assert series["2022-03-31"] is None
    assert series["2023-03-31"] == 20.0
    assert abs(series["2024-03-31"] - 25.0) < 1e-9


def test_build_latest_snapshot_prefers_computed():
    rows = [
        {"period_end_date": "2023-03-31", "metric_code": "REVENUE", "metric_value": 80},
        {"period_end_date": "2023-03-31", "metric_code": "NET_PROFIT", "metric_value": 10},
        {"period_end_date": "2023-03-31", "metric_code": "EQUITY_CAPITAL", "metric_value": 20},
        {"period_end_date": "2023-03-31", "metric_code": "RESERVES", "metric_value": 30},
        {"period_end_date": "2024-03-31", "metric_code": "REVENUE", "metric_value": 100},
        {"period_end_date": "2024-03-31", "metric_code": "NET_PROFIT", "metric_value": 20},
        {"period_end_date": "2024-03-31", "metric_code": "EQUITY_CAPITAL", "metric_value": 20},
        {"period_end_date": "2024-03-31", "metric_code": "RESERVES", "metric_value": 30},
    ]
    snap = build_latest_snapshot(rows, {"ROE": "1%"}, reporting_basis="CONSOLIDATED")
    assert snap["as_of"] == "2024-03-31"
    assert snap["calculation_method"] == CALC_VERSION
    assert snap["ratios"]["ROE"] == 40.0
    assert snap["methods"]["ROE"] == CALC_VERSION
    assert snap["ratios"]["REVENUE_GROWTH"] == 25.0


class _SnapshotCursor:
    def __init__(self):
        self.latest = None
        self.writes = []
        self.deletes = []
        self._phase = 0

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if "ORDER BY metric_date DESC" in text and "SELECT metric_date" in text:
            self._phase = 1
            return
        if "INSERT INTO market_data.stock_daily_metrics" in text:
            self.writes.append(params)
            self.latest = params[1]
            return
        if "DELETE FROM market_data.stock_daily_metrics" in text:
            self.deletes.append(params)
            return

    def fetchone(self):
        if self._phase == 1:
            self._phase = 0
            return (self.latest,) if self.latest else None
        return None


def test_upsert_latest_fundamental_ratios_is_idempotent_one_row():
    cur = _SnapshotCursor()
    stock_id = "11111111-1111-1111-1111-111111111111"
    snapshot = {
        "as_of": "2024-03-31",
        "reporting_basis": "CONSOLIDATED",
        "reporting_period": "ANNUAL",
        "calculation_method": CALC_VERSION,
        "ratios": {"ROE": 40.0},
        "methods": {"ROE": CALC_VERSION},
    }
    first = upsert_latest_fundamental_ratios(cur, stock_id, snapshot, "src")
    second = upsert_latest_fundamental_ratios(cur, stock_id, snapshot, "src")
    assert first == "2024-03-31"
    assert second == "2024-03-31"
    assert len(cur.writes) == 2
    assert len(cur.deletes) == 2
    assert cur.deletes[-1] == (stock_id, "2024-03-31")
    # Payload is a single bag — never a historical ratio series.
    raw = cur.writes[-1][2].adapted
    assert isinstance(raw["ratios"], dict)
    assert "history" not in raw
    json.dumps(raw)  # must be JSON-serializable
