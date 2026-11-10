"""Release 1.6: history depth presets for add / extend sync."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.market_data.history_period import (
    DEFAULT_HISTORY_PERIOD,
    HISTORY_PERIODS,
    history_period_from_date,
    normalize_history_period,
    yfinance_period,
)


def test_normalize_history_period_accepts_presets_and_default():
    assert normalize_history_period(None) == DEFAULT_HISTORY_PERIOD
    assert normalize_history_period("5Y") == "5y"
    assert normalize_history_period("10y") == "10y"
    assert normalize_history_period("max") == "max"
    assert normalize_history_period("", default=None) is None
    with pytest.raises(ValueError):
        normalize_history_period("3y")


def test_history_period_from_date_and_yfinance_mapping():
    assert history_period_from_date("max") is None
    assert history_period_from_date(None) is None
    five = history_period_from_date("5y")
    assert five == date.today() - timedelta(days=365 * 5 + 2)
    assert yfinance_period("5y") == "5y"
    assert yfinance_period("max") == "max"
    assert set(HISTORY_PERIODS) == {"5y", "10y", "max"}


def test_track_and_sync_routes_accept_history_period():
    routes = (ROOT / "backend_api" / "app" / "market_data_routes.py").read_text(encoding="utf-8")
    assert 'history_period: str = Query("5y")' in routes
    assert "history_period=period" in routes
    assert "sync_home_indexes(parts, history_period=period)" in routes or "history_period=period" in routes
    sync = (ROOT / "portfolio-service" / "backend" / "market_data" / "sync.py").read_text(encoding="utf-8")
    assert "history_period" in sync
    index_sync = (ROOT / "portfolio-service" / "backend" / "market_data" / "index_sync.py").read_text(
        encoding="utf-8"
    )
    assert "history_period" in index_sync
