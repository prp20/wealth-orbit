import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data import fx_rates


def test_usd_inr_rate_uses_api_and_caches(monkeypatch):
    calls = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "result": "success",
                "conversion_rate": 83.25,
                "time_last_update_utc": "Tue, 17 Nov 2026 00:00:00 +0000",
            }

    def fake_get(url, timeout=10):
        calls["n"] += 1
        assert "pair/USD/INR" in url
        assert "SECRET" in url
        return FakeResponse()

    monkeypatch.setenv("EXCHANGE_RATE_API_KEY", "SECRET")
    monkeypatch.setattr(fx_rates.requests, "get", fake_get)
    fx_rates._cache["payload"] = None
    fx_rates._cache["expires_at"] = 0.0

    first = fx_rates.usd_inr_rate()
    second = fx_rates.usd_inr_rate()
    assert first["rate"] == 83.25
    assert first["base"] == "USD"
    assert first["quote"] == "INR"
    assert second["rate"] == 83.25
    assert calls["n"] == 1


def test_usd_inr_rate_requires_api_key(monkeypatch):
    monkeypatch.delenv("EXCHANGE_RATE_API_KEY", raising=False)
    fx_rates._cache["payload"] = None
    fx_rates._cache["expires_at"] = 0.0
    with pytest.raises(RuntimeError, match="EXCHANGE_RATE_API_KEY"):
        fx_rates.usd_inr_rate()
