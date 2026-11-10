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


def test_builtin_quality_value_validates():
    path = ROOT / "screens" / "stock" / "built_in" / "quality_value.py"
    result = validate_screen_file(path, expected_asset_class="stock")
    assert result.ok, result.errors
    assert result.screen_id == "quality_value"
    assert result.meta["name"] == "Quality value"


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


def test_discover_lists_builtin_runnable_screens():
    payload = discover_screens(use_cache=False)
    ids = {item["screen_id"] for item in payload["screens"] if item["status"] == "ok"}
    assert "quality_value" in ids
    assert "high_dividend" in ids


def test_dry_run_builtin_quality_value():
    path = ROOT / "screens" / "stock" / "built_in" / "quality_value.py"
    result = dry_run_screen(path, timeout_seconds=15)
    assert result.get("ok") is True, result
    symbols = result.get("symbols") or []
    # Fixture AAA has pe=20, roe=0.16 → passes default max_pe=25 / min_roe=0.15
    assert "AAA" in symbols
    assert "BBB" not in symbols


def test_run_screen_honest_empty_snapshot(monkeypatch):
    import backend.screen_plugins.runner as runner

    monkeypatch.setattr(runner, "snapshot_records_for_plugins", lambda require_metrics=True: [])
    # Bypass discover cache requiring DB by stubbing get_runnable_screen
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
                    {"name": "min_roe", "type": "float", "default": 15.0},
                ],
            },
        },
    )
    monkeypatch.setattr(
        runner,
        "discover_screens",
        lambda use_cache=True: {"timeout_seconds": 15, "screens": []},
    )
    result = run_screen("quality_value", {"max_pe": 25, "min_roe": 15})
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


def test_refresh_screens_returns_payload():
    payload = refresh_screens()
    assert payload["asset_class"] == "stock"
    assert any(item["screen_id"] == "quality_value" and item["status"] == "ok" for item in payload["screens"])
