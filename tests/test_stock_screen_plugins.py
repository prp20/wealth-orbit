"""Release 1.7: stock screen plugin validate / discover / isolate."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))
sys.path.insert(0, str(ROOT))

from backend.screen_plugins.discovery import discover_screens, refresh_screens
from backend.screen_plugins.runner import dry_run_screen, run_screen
from backend.screen_plugins.validator import validate_screen_file

PLAYBOOK_IDS = [
    "consistent_compounders",
    "garp",
    "debt_free_high_growth",
    "magic_formula_in",
    "small_cap_hidden_gems",
    "cash_rich_undervalued",
    "momentum_fundamentals",
    "dividend_aristocrats_in",
    "turnaround_candidates",
    "capital_light_quality",
]


@pytest.mark.parametrize("screen_id", PLAYBOOK_IDS)
def test_playbook_builtin_validates(screen_id: str):
    path = ROOT / "screens" / "stock" / "built_in" / f"{screen_id}.py"
    result = validate_screen_file(path, expected_asset_class="stock")
    assert result.ok, result.errors
    assert result.screen_id == screen_id


@pytest.mark.parametrize("screen_id", PLAYBOOK_IDS)
def test_playbook_builtin_dry_run_keeps_strong_fixture(screen_id: str):
    path = ROOT / "screens" / "stock" / "built_in" / f"{screen_id}.py"
    result = dry_run_screen(path, timeout_seconds=15)
    assert result.get("ok") is True, result
    symbols = set(result.get("symbols") or [])
    assert "AAA" in symbols
    assert "BBB" not in symbols


def test_builtin_quality_value_validates():
    path = ROOT / "screens" / "stock" / "built_in" / "quality_value.py"
    result = validate_screen_file(path, expected_asset_class="stock")
    assert result.ok, result.errors
    assert result.screen_id == "quality_value"


def test_rejects_forbidden_import(tmp_path: Path):
    bad = tmp_path / "evil.py"
    bad.write_text(
        textwrap.dedent(
            """
            import os
            SCREEN_ID = "evil"
            SCREEN_META = {
                "name": "Evil",
                "version": "1.0.0",
                "description": "nope",
                "asset_class": "stock",
                "parameters": [],
            }
            def screen(stocks, params):
                return stocks
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    result = validate_screen_file(bad, expected_asset_class="stock")
    assert not result.ok
    assert any("forbidden import" in err for err in result.errors)


def test_rejects_missing_screen_fn(tmp_path: Path):
    bad = tmp_path / "noscreen.py"
    bad.write_text(
        textwrap.dedent(
            """
            SCREEN_ID = "noscreen"
            SCREEN_META = {
                "name": "No screen",
                "version": "1.0.0",
                "description": "missing fn",
                "asset_class": "stock",
                "parameters": [],
            }
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    result = validate_screen_file(bad, expected_asset_class="stock")
    assert not result.ok
    assert any("screen(stocks, params)" in err for err in result.errors)


def test_discover_lists_playbook_screens():
    payload = discover_screens(use_cache=False)
    ok_ids = {item["screen_id"] for item in payload["screens"] if item["status"] == "ok"}
    for screen_id in PLAYBOOK_IDS:
        assert screen_id in ok_ids
    assert "quality_value" in ok_ids
    assert "high_dividend" in ok_ids


def test_dry_run_builtin_quality_value():
    path = ROOT / "screens" / "stock" / "built_in" / "quality_value.py"
    result = dry_run_screen(path, timeout_seconds=15)
    assert result.get("ok") is True, result
    symbols = result.get("symbols") or []
    assert "AAA" in symbols
    assert "BBB" not in symbols


def test_run_screen_honest_empty_snapshot(monkeypatch):
    import backend.screen_plugins.runner as runner

    monkeypatch.setattr(runner, "snapshot_records_for_plugins", lambda require_metrics=True: [])
    monkeypatch.setattr(
        runner,
        "get_runnable_screen",
        lambda screen_id: {
            "screen_id": "quality_value",
            "path": "screens/stock/built_in/quality_value.py",
            "enabled": True,
            "status": "ok",
            "meta": {
                "name": "Quality value",
                "version": "1.0.0",
                "description": "x",
                "asset_class": "stock",
                "parameters": [
                    {"name": "max_pe", "type": "float", "default": 25.0},
                    {"name": "min_roe", "type": "float", "default": 0.15},
                ],
            },
        },
    )
    monkeypatch.setattr(
        runner,
        "discover_screens",
        lambda use_cache=True: {"timeout_seconds": 15, "screens": []},
    )
    result = run_screen("quality_value", {"max_pe": 25, "min_roe": 0.15})
    assert result["ok"] is False
    assert "no stored stock metrics" in result["error"]


def test_routes_and_ui_wire_stock_screener():
    routes = (ROOT / "backend_api" / "app" / "market_data_routes.py").read_text(encoding="utf-8")
    assert '@router.get("/stocks/screen")' in routes
    assert '@router.get("/stocks/screens")' in routes
    assert '@router.post("/stocks/screens/refresh")' in routes
    assert '@router.post("/stocks/screens/{screen_id}/run")' in routes
    app = (ROOT / "frontend-react" / "src" / "app" / "App.tsx").read_text(encoding="utf-8")
    assert 'path="/stocks/screen"' in app
    assert "StockScreenerPage" in app
    stocks = (ROOT / "frontend-react" / "src" / "pages" / "stocks" / "StockListPage.tsx").read_text(
        encoding="utf-8"
    )
    assert 'to="/stocks/screen"' in stocks
    assert "Screener" in stocks
    readme = (ROOT / "screens" / "README.md").read_text(encoding="utf-8")
    assert "market_cap_cr" in readme
    assert "consistent_compounders" in readme


def test_refresh_screens_returns_playbook():
    payload = refresh_screens()
    assert payload["asset_class"] == "stock"
    ok = {item["screen_id"] for item in payload["screens"] if item["status"] == "ok"}
    for screen_id in PLAYBOOK_IDS:
        assert screen_id in ok, f"{screen_id} missing/failed: {[i for i in payload['screens'] if i['screen_id']==screen_id]}"


def test_snapshot_exposes_expanded_columns():
    from backend.market_data.stock_screen import SNAPSHOT_COLUMNS

    for column in (
        "market_cap_cr",
        "earnings_yield",
        "debt_to_equity",
        "profit_growth_3y",
        "promoter_holding",
        "sma_200",
        "roa",
    ):
        assert column in SNAPSHOT_COLUMNS
