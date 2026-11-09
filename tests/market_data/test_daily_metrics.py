import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.daily_metrics import (
    calculate_fallback_metrics,
    net_debt_from_parts,
    normalize_yahoo_dividend_yield,
    provider_metrics_from_ratios,
    yahoo_daily_metric_fields,
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


def test_normalize_yahoo_dividend_yield_stores_percent_points_once():
    assert normalize_yahoo_dividend_yield(0.015) == 1.5
    assert normalize_yahoo_dividend_yield(1.5) == 1.5
    assert normalize_yahoo_dividend_yield(1.0) == 1.0
    assert normalize_yahoo_dividend_yield(0) == 0.0
    assert normalize_yahoo_dividend_yield(150) is None
    assert normalize_yahoo_dividend_yield(None) is None
    assert normalize_yahoo_dividend_yield("bad") is None


def test_yahoo_daily_metric_fields_never_store_forward_peg():
    fields = yahoo_daily_metric_fields(
        {
            "marketCap": 1_000_000,
            "dividendYield": 0.012,
            "totalDebt": 100,
            "totalCash": 40,
            "pegRatio": 2.5,
            "forwardPegRatio": 3.1,
            "trailingPegRatio": 1.8,
        }
    )
    assert fields["peg"] is None
    assert fields["dividend_yield"] == 1.2
    assert fields["net_debt"] == 60
    assert "pegRatio" not in fields
    assert "forwardPegRatio" not in fields
