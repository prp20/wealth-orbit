"""Technicals are computed from OHLC and persisted for the latest trading day only."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend import reference_service
from backend.market_data import sync as stock_sync


def _ohlc_frame(days: int = 40) -> pd.DataFrame:
    start = date(2024, 1, 1)
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=i) for i in range(days)],
            "open": [1.0 + i * 0.01 for i in range(days)],
            "high": [1.2 + i * 0.01 for i in range(days)],
            "low": [0.9 + i * 0.01 for i in range(days)],
            "close": [1.1 + i * 0.01 for i in range(days)],
            "volume": [10 + i for i in range(days)],
        }
    )


def test_stock_technical_indicators_falls_back_to_history_compute():
    history = pd.DataFrame(
        {
            "date": [date(2024, 1, i) for i in range(1, 31)],
            "open": [100.0] * 30,
            "high": [101.0] * 30,
            "low": [99.0] * 30,
            "close": [100.0 + (i / 10) for i in range(30)],
            "raw_close": [100.0] * 30,
            "adj_close": [None] * 30,
            "volume": [1000] * 30,
            "is_adjusted": [False] * 30,
        }
    )
    with (
        patch.object(reference_service, "_load_stored_technicals", return_value=(reference_service._empty_technicals(), None)),
        patch.object(reference_service, "_last_ohlc_date", return_value=None),
        patch.object(reference_service, "stock_history", return_value=history),
    ):
        frame = reference_service.stock_technical_indicators("HDFCBANK")
    assert not frame.empty
    assert "indicator_value" in frame.columns
    assert "SMA" in set(frame["indicator_code"])
    assert "MACD" in set(frame["indicator_code"])
    assert (frame["calculation_status"] == "CURRENT").all()
    assert frame["date"].nunique() == 1


def test_sync_technical_indicators_persists_latest_day(monkeypatch):
    frame = _ohlc_frame(40)
    captured: dict = {}

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, *args, **kwargs):
            return None

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return _Cursor()

        def commit(self):
            return None

        def close(self):
            return None

    def fake_persist(cur, stock_id, trading_date, rows):
        captured["trading_date"] = trading_date
        captured["rows"] = len(rows)
        captured["dates"] = set(str(d)[:10] for d in rows["date"].tolist())
        return len(rows)

    monkeypatch.setattr(stock_sync, "_connect", lambda *a, **k: _Conn())
    monkeypatch.setattr(stock_sync, "_prices", lambda cur, symbol: ("stock-id", frame))
    monkeypatch.setattr(stock_sync, "_persist_latest_technicals", fake_persist)
    monkeypatch.setattr(stock_sync, "_run_writable", lambda op, **k: op())

    result = stock_sync.sync_technical_indicators("HDFCBANK", force=True)
    assert result["status"] == "completed"
    assert result["persisted"] is True
    assert result["records_processed"] == captured["rows"]
    assert captured["trading_date"] == frame["date"].max()
    assert captured["dates"] == {str(frame["date"].max())}


def test_latest_indicator_rows_keeps_only_last_date():
    frame = _ohlc_frame(50)
    trading_date, rows = stock_sync._latest_indicator_rows(frame)
    assert trading_date == frame["date"].max()
    assert set(str(d)[:10] for d in rows["date"].tolist()) == {str(trading_date)}
