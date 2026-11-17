"""Technicals on read return stored latest-day rows only (no ephemeral OHLC compute)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_stock_technical_indicators_empty_without_ephemeral_compute():
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
    assert frame.empty


def test_stock_technical_indicators_view_reports_sync_error_when_not_stored():
    with (
        patch.object(reference_service, "_load_stored_technicals", return_value=(reference_service._empty_technicals(), None)),
        patch.object(reference_service, "_last_ohlc_date", return_value=None),
        patch.object(reference_service, "_latest_technical_sync_job_error", return_value=None),
    ):
        payload = reference_service.stock_technical_indicators_view("HDFCBANK")
    assert payload["records"] == []
    assert payload["stored_only"] is True
    assert payload["sync_error"] == "sync_prices_before_technicals"


def test_stock_technical_indicators_view_surfaces_failed_sync_job():
    with (
        patch.object(reference_service, "_load_stored_technicals", return_value=(reference_service._empty_technicals(), None)),
        patch.object(reference_service, "_last_ohlc_date", return_value=date(2024, 6, 1)),
        patch.object(stock_sync, "sync_technical_indicators", side_effect=RuntimeError("db read-only")),
        patch.object(
            reference_service,
            "_latest_technical_sync_job_error",
            return_value="yahoo_empty_info",
        ),
    ):
        payload = reference_service.stock_technical_indicators_view("HDFCBANK")
    assert payload["records"] == []
    assert payload["sync_error"] == "db read-only"


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
    assert result["calculation_version"] == stock_sync.TECHNICAL_CALCULATION_VERSION
    assert result["indicator_requests"] == stock_sync.DEFAULT_INDICATORS
    assert captured["trading_date"] == frame["date"].max()
    assert captured["dates"] == {str(frame["date"].max())}


def test_latest_indicator_rows_keeps_only_last_date():
    frame = _ohlc_frame(250)
    trading_date, rows = stock_sync._latest_indicator_rows(frame)
    assert trading_date == frame["date"].max()
    assert set(str(d)[:10] for d in rows["date"].tolist()) == {str(trading_date)}
    assert "STOCH" in set(rows["indicator_code"])
    assert "SMA" in set(rows["indicator_code"])
    assert {50, 200} <= set(rows.loc[rows["indicator_code"] == "SMA", "indicator_period"])


def test_resolve_stored_returns_persisted_rows_without_recompute():
    stored = pd.DataFrame(
        [
            {
                "date": date(2024, 6, 1),
                "indicator_code": "RSI",
                "indicator_period": 14,
                "parameters": "{}",
                "component": "",
                "indicator_value": 55.0,
                "calculation_status": "CURRENT",
                "calculated_at": date(2024, 6, 1),
            }
        ]
    )
    with (
        patch.object(reference_service, "_load_stored_technicals", return_value=(stored, date(2024, 6, 1))),
        patch.object(reference_service, "_last_ohlc_date", return_value=date(2024, 6, 1)),
        patch.object(stock_sync, "sync_technical_indicators", MagicMock()) as sync_mock,
    ):
        frame, err = reference_service._resolve_stored_technical_indicators("HDFCBANK")
    assert err is None
    assert len(frame) == 1
    sync_mock.assert_not_called()