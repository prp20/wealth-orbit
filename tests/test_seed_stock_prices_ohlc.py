"""OHLC sanitization for Yahoo bars that violate chk_stock_price_values."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service" / "scripts" / "seed"))

from seed_stock_prices import _sanitize_ohlc


def test_sanitize_expands_high_when_open_above_high():
    # Failing production bar shape: open 4725, high/low/close 4650.
    result = _sanitize_ohlc(4725.0, 4650.0, 4650.0, 4650.0)
    assert result == (4725.0, 4725.0, 4650.0, 4650.0)


def test_sanitize_expands_low_when_close_below_low():
    result = _sanitize_ohlc(100.0, 110.0, 95.0, 90.0)
    assert result == (100.0, 110.0, 90.0, 90.0)


def test_sanitize_rejects_non_positive():
    assert _sanitize_ohlc(0.0, 1.0, 1.0, 1.0) is None
    assert _sanitize_ohlc(1.0, 1.0, -1.0, 1.0) is None
    assert _sanitize_ohlc(None, 1.0, 1.0, 1.0) is None
