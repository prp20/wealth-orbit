"""Release 1.6: resolve/upsert instrument registry and track API wiring."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))
sys.path.insert(0, str(ROOT))

from backend.market_data import instrument_registry as registry
from backend.market_data.instrument_registry import (
    InstrumentResolveError,
    normalize_index_code,
    normalize_scheme_code,
    normalize_stock_symbol,
)


def test_normalize_stock_symbol_rejects_garbage_and_bse_suffix():
    assert normalize_stock_symbol(" reliance ") == "RELIANCE"
    assert normalize_stock_symbol("INFY.NS") == "INFY"
    with pytest.raises(InstrumentResolveError) as bse:
        normalize_stock_symbol("INFY.BO")
    assert bse.value.reason == "exchange_not_supported"
    with pytest.raises(InstrumentResolveError) as bad:
        normalize_stock_symbol("***")
    assert bad.value.reason == "invalid_symbol"


def test_normalize_scheme_and_index_codes():
    assert normalize_scheme_code("120503") == "120503"
    with pytest.raises(InstrumentResolveError) as scheme:
        normalize_scheme_code("ABC")
    assert scheme.value.reason == "invalid_scheme_code"
    assert normalize_index_code("nifty-50") == "NIFTY50"
    with pytest.raises(InstrumentResolveError) as index:
        normalize_index_code("1")
    assert index.value.reason == "invalid_index_code"


def test_resolve_index_allowlist_and_requires_yf_for_unknown(monkeypatch):
    monkeypatch.setattr(registry, "_load_seed_index_map", lambda: {"NIFTY50": "^NSEI"})
    resolved = registry.resolve_index("NIFTY50")
    assert resolved["yf_symbol"] == "^NSEI"
    assert resolved["index_code"] == "NIFTY50"

    with pytest.raises(InstrumentResolveError) as missing:
        registry.resolve_index("CUSTOMINDIA")
    assert missing.value.reason == "yf_symbol_required"

    with pytest.raises(InstrumentResolveError) as us:
        registry.resolve_index("CUSTOMINDIA", "SPY")
    assert us.value.reason == "index_not_india"

    # Lone caret symbols are not an India bypass.
    with pytest.raises(InstrumentResolveError) as caret:
        registry.resolve_index("CUSTOMINDIA", "^GSPC")
    assert caret.value.reason == "index_not_india"

    # Explicit NSE Yahoo symbols remain allowed.
    ok = registry.resolve_index("CUSTOMINDIA", "NIFTYMIDCAP150.NS")
    assert ok["yf_symbol"] == "NIFTYMIDCAP150.NS"


def test_fund_details_reject_empty_provider_dict():
    assert registry._fund_details_look_valid({}, "120503") is False
    assert registry._fund_details_look_valid({"scheme_name": "Foo"}, "120503") is True
    assert registry._fund_details_look_valid({"scheme_code": "120503"}, "120503") is True
    assert registry._fund_details_look_valid({"scheme_code": "999"}, "120503") is False


def test_resolve_stock_uses_yfinance_proof(monkeypatch):
    import types

    class FakeTicker:
        info = {"shortName": "Reliance Industries", "quoteType": "EQUITY", "regularMarketPrice": 100.0}

        def history(self, period="5d"):
            return SimpleNamespace(empty=False)

    fake_module = types.ModuleType("yfinance")
    fake_module.Ticker = lambda _symbol: FakeTicker()
    monkeypatch.setitem(sys.modules, "yfinance", fake_module)

    result = registry.resolve_stock("reliance")
    assert result["trading_symbol"] == "RELIANCE"
    assert result["company_name"] == "Reliance Industries"


def test_ensure_stock_idempotent_with_fake_upsert(monkeypatch):
    monkeypatch.setattr(
        registry,
        "resolve_stock",
        lambda symbol: {
            "instrument_type": "stock",
            "exchange": "NSE",
            "trading_symbol": "RELIANCE",
            "company_name": "Reliance Industries",
        },
    )
    calls = {"n": 0}

    def fake_upsert(resolved):
        calls["n"] += 1
        master = {
            "stock_id": "1",
            "trading_symbol": resolved["trading_symbol"],
            "exchange": "NSE",
            "company_name": resolved["company_name"],
        }
        return master, calls["n"] == 1

    monkeypatch.setattr(registry, "upsert_stock", fake_upsert)
    first = registry.ensure_stock("RELIANCE")
    second = registry.ensure_stock("RELIANCE")
    assert first["status"] == "created"
    assert second["status"] == "existing"
    assert second["already_tracked"] is True


def test_track_routes_enqueue_history_kinds():
    routes = (ROOT / "backend_api" / "app" / "market_data_routes.py").read_text(encoding="utf-8")
    assert 'POST "/instruments/stocks"' in routes or "@router.post(\"/instruments/stocks\")" in routes
    assert 'enqueue("STOCK"' in routes and '"PRICES"' in routes
    assert 'enqueue("MUTUAL_FUND"' in routes and '"MF_NAV"' in routes
    assert "HOME_INDEX_ENTITY" in routes
    assert "Depends(current_user)" in routes
    assert "InstrumentResolveError" in inspect.getsource(
        __import__("backend.market_data.instrument_registry", fromlist=["InstrumentResolveError"])
    )


def test_upsert_index_refuses_yahoo_mapping_steal(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params=None):
            self.calls.append((sql, params))
            self._sql = sql
            self._params = params

        def fetchone(self):
            sql = self._sql
            if "FROM market_data.index_reference" in sql:
                return None
            if "FROM market_data.index_provider_mappings" in sql and "trading_symbol" in sql:
                # Existing mapping for ^NSEI belongs to a different index.
                return ("other-index-id", True)
            if "RETURNING index_id" in sql:
                return ("new-index-id",)
            return None

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(registry, "_connection", lambda: FakeConn())
    monkeypatch.setattr(registry, "ensure_data_source", lambda cur, name: "source")
    with pytest.raises(InstrumentResolveError) as exc:
        registry.upsert_index(
            {
                "index_code": "CUSTOM",
                "index_name": "Custom",
                "yf_symbol": "^NSEI",
            }
        )
    assert exc.value.reason == "yf_symbol_in_use"
