"""Derived screen snapshot flags (latest OHLC only)."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.market_data.screen_derived import DERIVED_SCREEN_COLUMNS, apply_derived_screen_fields
from backend.market_data.stock_screen import SNAPSHOT_COLUMNS


def _row(**overrides) -> dict:
    base = {
        "price_close": 110.0,
        "sma_50": 100.0,
        "sma_200": 90.0,
        "latest_volume": 150_000.0,
        "vol_avg_20": 100_000.0,
        "high_52w": 120.0,
        "low_52w": 80.0,
        "bb_upper": 115.0,
        "bb_lower": 95.0,
    }
    base.update(overrides)
    return base


def test_apply_derived_screen_fields_computes_expected_values():
    frame = apply_derived_screen_fields(pd.DataFrame([_row()]))
    row = frame.iloc[0]
    assert bool(row["price_above_sma_50"]) is True
    assert bool(row["price_above_sma_200"]) is True
    assert row["pct_from_sma_50"] == pytest.approx(0.10)
    assert row["pct_from_sma_200"] == pytest.approx(110.0 / 90.0 - 1.0)
    assert bool(row["sma50_above_sma200"]) is True
    assert row["rel_volume_20"] == pytest.approx(1.5)
    assert row["pct_from_52w_high"] == pytest.approx(110.0 / 120.0 - 1.0)
    assert row["pct_from_52w_low"] == pytest.approx(110.0 / 80.0 - 1.0)
    assert row["bb_percent_b"] == pytest.approx(0.75)


def test_apply_derived_screen_fields_null_when_inputs_missing():
    frame = apply_derived_screen_fields(
        pd.DataFrame([{"price_close": 50.0, "sma_50": None, "sma_200": None}])
    )
    row = frame.iloc[0]
    assert pd.isna(row["price_above_sma_50"])
    assert pd.isna(row["rel_volume_20"])
    assert pd.isna(row["pct_from_52w_high"])


def test_snapshot_allowlist_includes_derived_columns():
    for column in DERIVED_SCREEN_COLUMNS:
        assert column in SNAPSHOT_COLUMNS


def test_build_stock_metrics_snapshot_applies_derived_fields(monkeypatch):
    from backend.market_data import stock_screen

    raw = pd.DataFrame(
        [
            {
                "trading_symbol": "AAA",
                "company_name": "Alpha",
                "exchange": "NSE",
                "sector_name": "Tech",
                "industry_name": "IT",
                "market_cap_class": "Large",
                "price_close": 100.0,
                "sma_50": 95.0,
                "sma_200": 90.0,
                "latest_volume": 200.0,
                "vol_avg_20": 100.0,
                "high_52w": 110.0,
                "low_52w": 80.0,
                "bb_upper": 105.0,
                "bb_lower": 90.0,
                "market_cap": 1e10,
                "metrics_date": "2026-01-01",
            }
        ]
    )
    monkeypatch.setattr(stock_screen, "_query", lambda sql: raw)
    frame = stock_screen.build_stock_metrics_snapshot()
    row = frame.iloc[0]
    assert row["sma_50"] == pytest.approx(95.0)
    assert bool(row["price_above_sma_50"]) is True
    assert row["rel_volume_20"] == pytest.approx(2.0)
    assert row["pct_from_52w_high"] == pytest.approx(100.0 / 110.0 - 1.0)
    assert "latest_volume" not in frame.columns