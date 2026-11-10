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


def test_ui_labels_history_depth_and_empty_cta_are_wired():
    fe = ROOT / "frontend-react" / "src"
    stocks = (fe / "pages" / "stocks" / "StockListPage.tsx").read_text(encoding="utf-8")
    funds = (fe / "pages" / "funds" / "FundListPage.tsx").read_text(encoding="utf-8")
    dialog = (fe / "components" / "AddInstrumentDialog.tsx").read_text(encoding="utf-8")
    sync_btn = (fe / "components" / "SyncJobButton.tsx").read_text(encoding="utf-8")
    stock_detail = (fe / "pages" / "stocks" / "StockDetailPage.tsx").read_text(encoding="utf-8")
    fund_detail = (fe / "pages" / "funds" / "FundDetailPage.tsx").read_text(encoding="utf-8")
    home = (fe / "pages" / "DashboardPage.tsx").read_text(encoding="utf-8")
    assert "Add stock" in stocks
    assert "Add fund" in funds
    assert "History depth" in dialog
    assert "historyPeriod" in dialog
    assert "trackStockInstrument(trimmed, true, historyPeriod)" in dialog
    assert "removeQueries({ queryKey: ['stock', symbol] })" in dialog
    assert "removeQueries({ queryKey: ['fund', scheme] })" in dialog
    assert "Extend history" in sync_btn
    assert "Not in catalog" in stock_detail
    assert "Not in catalog" in fund_detail
    assert "extendHistory" in stock_detail
    assert "MAX_HOME_EXTRA_INDEXES" in home


def test_nav_deepen_bypasses_watermark_when_history_period_set():
    nav = (
        ROOT / "portfolio-service" / "backend" / "mutual_fund_service.py"
    ).read_text(encoding="utf-8")
    assert "deepen = history_period is not None" in nav
    assert "if not force and not deepen:" in nav


def test_index_add_job_identity_is_not_home_indexes():
    routes = (ROOT / "backend_api" / "app" / "market_data_routes.py").read_text(encoding="utf-8")
    track_index = routes.split("def track_index_instrument")[1].split("@router.get(\"/stocks\")")[0]
    assert "HOME_INDEX_ENTITY" not in track_index
    assert '"STOCK"' in track_index
    assert "code," in track_index
    assert '"PRICES"' in track_index
    assert "entity_key" in track_index
    preview_block = routes.split("def preview_stock_instrument")[1].split("def stock_list")[0]
    assert "Depends(current_user)" in preview_block
