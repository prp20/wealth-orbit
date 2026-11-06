import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.daily_metrics import (
    calculate_fallback_metrics,
    net_debt_from_parts,
    provider_metrics_from_ratios,
)


def test_provider_metrics_normalizes_supported_screener_ratio_labels():
    metrics, warnings = provider_metrics_from_ratios(
        {
            "Market Cap": "1,25,000 Cr.",
            "Stock P/E": "23.4",
            "Price to Book Value": "4.2",
            "Dividend Yield": "1.5%",
            "ROCE": "21.0%",
            "ROE": "18.2%",
        }
    )

    assert metrics == {
        "market_cap": 125000.0,
        "pe_ratio": 23.4,
        "pb_ratio": 4.2,
        "dividend_yield": 1.5,
        "roce": 21.0,
        "roe": 18.2,
    }
    assert warnings == []


def test_fallback_metrics_only_uses_reliable_nonzero_inputs():
    assert calculate_fallback_metrics(close=120.0, eps=10.0, book_value=30.0, dividend_per_share=3.0) == {
        "pe_ratio": 12.0,
        "pb_ratio": 4.0,
        "dividend_yield": 2.5,
    }
    assert calculate_fallback_metrics(close=120.0, eps=0.0, book_value=None, dividend_per_share=None) == {}


def test_net_debt_requires_both_sides_and_keeps_zero():
    assert net_debt_from_parts(100, 40) == 60
    assert net_debt_from_parts(100, None) is None
    assert net_debt_from_parts(None, 40) is None
    assert net_debt_from_parts(0, 10) == -10
