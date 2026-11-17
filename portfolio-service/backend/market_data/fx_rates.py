"""Live FX helpers (USD/INR via ExchangeRate-API)."""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("wealth_orbit.fx")

_CACHE_TTL_SECONDS = 30 * 60
_cache: dict[str, Any] = {"expires_at": 0.0, "payload": None}


def usd_inr_rate(*, force_refresh: bool = False) -> dict[str, Any]:
    """Return USD→INR conversion rate. Uses EXCHANGE_RATE_API_KEY from env."""
    now = time.time()
    if not force_refresh and _cache["payload"] and now < float(_cache["expires_at"]):
        return dict(_cache["payload"])

    api_key = (os.environ.get("EXCHANGE_RATE_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("EXCHANGE_RATE_API_KEY is not configured")

    url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/USD/INR"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    if str(data.get("result") or "").lower() == "error":
        raise RuntimeError(str(data.get("error-type") or "exchange_rate_error"))

    rate = data.get("conversion_rate")
    if rate is None:
        raise RuntimeError("conversion_rate missing from exchange response")

    payload = {
        "base": "USD",
        "quote": "INR",
        "rate": float(rate),
        "as_of": data.get("time_last_update_utc") or data.get("time_last_update_unix"),
        "provider": "exchangerate-api",
    }
    _cache["payload"] = payload
    _cache["expires_at"] = now + _CACHE_TTL_SECONDS
    logger.info("fx refreshed pair=USD/INR rate=%s", payload["rate"])
    return dict(payload)
