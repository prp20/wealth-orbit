"""Tests for backend_api.app.technical_indicators (pandas OHLC path used by sync)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "portfolio-service"))

from backend.market_data.sync import (
    DEFAULT_INDICATORS,
    TECHNICAL_CALCULATION_VERSION,
    _latest_indicator_rows,
)
from backend_api.app.technical_indicators import calculate_indicators


def _ohlc(days: int, start: date | None = None) -> pd.DataFrame:
    start = start or date(2024, 1, 1)
    i = range(days)
    close = [50.0 + n * 0.5 + (n % 7) * 0.2 for n in i]
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=n) for n in i],
            "open": close,
            "high": [c + 1.0 for c in close],
            "low": [c - 1.0 for c in close],
            "close": close,
            "volume": [1000 + n for n in i],
        }
    )


def test_default_indicators_catalog_matches_release_1_10():
    codes = [(row["code"], row["parameters"]) for row in DEFAULT_INDICATORS]
    assert ("SMA", {"period": 50}) in codes
    assert ("SMA", {"period": 200}) in codes
    assert ("EMA", {"period": 50}) in codes
    assert ("STOCH", {"k_period": 14, "d_period": 3}) in codes
    assert TECHNICAL_CALCULATION_VERSION == "tech_v1"


def test_sma_50_and_200_emit_on_long_history():
    frame = _ohlc(260)
    out = calculate_indicators(frame, [
        {"code": "SMA", "parameters": {"period": 50}},
        {"code": "SMA", "parameters": {"period": 200}},
    ])
    latest = frame["date"].max()
    latest_rows = out[(out["date"] == latest) & (out["component"] == "VALUE")]
    periods = set(latest_rows["indicator_period"])
    assert periods == {50, 200}
    assert latest_rows["value"].notna().all()


def test_stochastic_k_and_d_components():
    frame = _ohlc(40)
    out = calculate_indicators(frame, [{"code": "STOCH", "parameters": {"k_period": 14, "d_period": 3}}])
    latest = frame["date"].max()
    day = out[out["date"] == latest]
    assert set(day["component"]) == {"K", "D"}
    assert day["value"].notna().all()
    k = float(day.loc[day["component"] == "K", "value"].iloc[0])
    d = float(day.loc[day["component"] == "D", "value"].iloc[0])
    assert 0 <= k <= 100
    assert 0 <= d <= 100


def test_latest_indicator_rows_include_new_families_latest_only():
    frame = _ohlc(260)
    trading_date, rows = _latest_indicator_rows(frame)
    assert trading_date == frame["date"].max()
    assert set(str(d)[:10] for d in rows["date"]) == {str(trading_date)}
    codes = set(rows["indicator_code"])
    assert {"SMA", "EMA", "STOCH"}.issubset(codes)
    sma_periods = set(rows.loc[rows["indicator_code"] == "SMA", "indicator_period"])
    assert sma_periods >= {20, 50, 200}
    stoch = rows[rows["indicator_code"] == "STOCH"]
    assert set(stoch["component"]) == {"K", "D"}


def test_persist_latest_technicals_passes_calculation_version(monkeypatch):
    from unittest.mock import MagicMock
    from backend.market_data import sync as stock_sync
    import uuid

    captured: list = []

    def fake_execute_values(cur, sql, values, **kwargs):
        captured.extend(values)

    monkeypatch.setattr(stock_sync, "execute_values", fake_execute_values)
    monkeypatch.setattr(stock_sync, "prune_non_latest_technical_dates", lambda *a, **k: 0)

    frame = _ohlc(260)
    _, rows = _latest_indicator_rows(frame)
    stock_sync._persist_latest_technicals(MagicMock(), uuid.uuid4(), frame["date"].max(), rows)
    assert captured
    assert all(row[-1] == TECHNICAL_CALCULATION_VERSION for row in captured)