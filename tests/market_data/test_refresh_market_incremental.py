"""Unit tests for CI incremental market refresh helpers (no network)."""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pytest


def _import_helpers():
    path = (
        Path(__file__).resolve().parents[2]
        / "portfolio-service"
        / "scripts"
        / "ci"
        / "refresh_market_incremental.py"
    )
    spec = importlib.util.spec_from_file_location("refresh_market_incremental", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing dotenv side effects against a missing DATABASE_URL during import
    # by loading only after we patch env in tests that need the module.
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def refresh_mod():
    return _import_helpers()


def test_stock_from_date_looks_back_from_watermark(refresh_mod):
    wm = date(2026, 11, 20)
    assert refresh_mod.stock_from_date(wm) == wm - timedelta(days=7)


def test_stock_from_date_without_watermark(refresh_mod):
    assert refresh_mod.stock_from_date(None) == date.today() - timedelta(days=14)


def test_assert_no_vault_secrets_blocks_ci(refresh_mod, monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("PORTFOLIO_ENCRYPTION_SECRET", "should-not-be-here")
    with pytest.raises(SystemExit, match="PORTFOLIO_ENCRYPTION_SECRET"):
        refresh_mod.assert_no_vault_secrets()


def test_assert_no_vault_secrets_allows_local(refresh_mod, monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("PORTFOLIO_ENCRYPTION_SECRET", "ok-locally")
    refresh_mod.assert_no_vault_secrets()


def test_require_database_url(refresh_mod, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="DATABASE_URL"):
        refresh_mod.require_database_url()
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    assert refresh_mod.require_database_url() == "postgresql://x"
