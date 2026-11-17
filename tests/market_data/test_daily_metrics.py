import math
import sys
from datetime import date

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.daily_metrics import (
    calculate_fallback_metrics,
    merge_screener_provider_fields,
    merge_yahoo_daily_fields,
    net_debt_from_parts,
    normalize_yahoo_dividend_yield,
    provider_metrics_from_ratios,
    upsert_screener_provider_metrics,
    yahoo_daily_metric_fields,
)
from backend.market_data import sync as stock_sync
from backend.market_data.providers.screener import ScreenerParser
from pathlib import Path as _Path
from uuid import uuid4


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
        "market_cap": 1_250_000_000_000.0,
        "pe_ratio": 23.4,
        "pb_ratio": 4.2,
        "dividend_yield": 1.5,
        "roce": 0.21,
        "roe": 0.182,
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
    assert net_debt_from_parts(float("nan"), 10) is None
    assert net_debt_from_parts(100, "bad") is None


def test_normalize_yahoo_dividend_yield_stores_percent_points_once():
    # Yahoo .NS typically returns a decimal fraction under 0.2.
    assert normalize_yahoo_dividend_yield(0.015) == 1.5
    assert normalize_yahoo_dividend_yield(0.012) == 1.2
    # Already-percent values, including sub-1%, stay as percent points.
    assert normalize_yahoo_dividend_yield(1.5) == 1.5
    assert normalize_yahoo_dividend_yield(0.8) == 0.8
    assert normalize_yahoo_dividend_yield(1.0) == 1.0
    assert normalize_yahoo_dividend_yield(0) == 0.0
    assert normalize_yahoo_dividend_yield(150) is None
    assert normalize_yahoo_dividend_yield(None) is None
    assert normalize_yahoo_dividend_yield("bad") is None
    assert normalize_yahoo_dividend_yield(float("nan")) is None
    assert normalize_yahoo_dividend_yield(float("inf")) is None
    assert normalize_yahoo_dividend_yield(-0.01) is None


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


def test_merge_screener_provider_fields_fills_nulls_only():
    merged, filled = merge_screener_provider_fields(
        {"roce": None, "stock_pe": 18.0, "roe": None},
        {"roce": 0.139, "pe_ratio": 99.0, "roe": 0.056},
    )
    assert merged["roce"] == 0.139
    assert merged["stock_pe"] == 18.0
    assert merged["roe"] == 0.056
    assert set(filled) == {"roce", "roe"}


class _ScreenerMetricsCursor:
    def __init__(self) -> None:
        self.rows: dict[tuple, dict] = {}
        self._fetch = False

    def execute(self, sql, params=None) -> None:
        text = " ".join(sql.split())
        if "ORDER BY metric_date DESC" in text and "SELECT metric_date" in text:
            self._fetch = True
            return
        if text.startswith("UPDATE market_data.stock_daily_metrics"):
            stock_id, metric_date = params[-2], params[-1]
            key = (stock_id, metric_date)
            row = self.rows[key]
            row.update(
                {
                    "market_cap": params[0],
                    "stock_pe": params[1],
                    "price_to_book": params[2],
                    "dividend_yield": params[3],
                    "book_value": params[4],
                    "roce": params[5],
                    "roe": params[6],
                }
            )
            if params[7] is not None:
                patch = params[7].adapted if hasattr(params[7], "adapted") else params[7]
                base = row.get("fundamental_ratios") or {}
                row["fundamental_ratios"] = {**base, **patch}
            return
        if text.startswith("INSERT INTO market_data.stock_daily_metrics"):
            stock_id, metric_date = params[0], params[1]
            bag = params[-1]
            bag_val = bag.adapted if hasattr(bag, "adapted") else bag
            self.rows[(stock_id, metric_date)] = {
                "stock_id": stock_id,
                "metric_date": metric_date,
                "market_cap": params[2],
                "stock_pe": params[3],
                "price_to_book": params[4],
                "dividend_yield": params[5],
                "book_value": params[6],
                "roce": params[7],
                "roe": params[8],
                "fundamental_ratios": bag_val,
            }
            return
        if "DELETE FROM market_data.stock_daily_metrics" in text and params:
            stock_id, keep = params
            for key in list(self.rows):
                if key[0] == stock_id and key[1] != keep:
                    del self.rows[key]

    def fetchone(self):
        if not self._fetch:
            return None
        self._fetch = False
        if not self.rows:
            return None
        key = max(self.rows, key=lambda item: item[1])
        row = self.rows[key]
        return (
            row["metric_date"],
            row.get("market_cap"),
            row.get("stock_pe"),
            row.get("price_to_book"),
            row.get("dividend_yield"),
            row.get("book_value"),
            row.get("roce"),
            row.get("roe"),
            row.get("fundamental_ratios"),
        )


def test_afcons_fixture_roce_lands_on_latest_metrics_row():
    fixture = (_Path(__file__).resolve().parents[1] / "fixtures/screener/afcons_ratios.html").read_text()
    stock_id = uuid4()
    parsed = ScreenerParser().parse(fixture, stock_id=stock_id)
    cur = _ScreenerMetricsCursor()
    metric_date = upsert_screener_provider_metrics(
        cur, stock_id, parsed.ratios, "screener-src-id", metric_date_fallback=None
    )
    assert metric_date is not None
    only = next(iter(cur.rows.values()))
    assert only["roce"] == pytest.approx(0.139)
    assert only["roe"] == pytest.approx(0.0561)
    assert only["market_cap"] == pytest.approx(8_163 * 10_000_000)
    assert only["fundamental_ratios"]["provider_metric_sources"]["roce"] == "screener"


def test_screener_metrics_do_not_overwrite_existing_yahoo_roce():
    stock_id = uuid4()
    cur = _ScreenerMetricsCursor()
    metric_day = date(2024, 6, 1)
    cur.rows[(stock_id, metric_day)] = {
        "stock_id": stock_id,
        "metric_date": metric_day,
        "market_cap": 1e9,
        "stock_pe": 20.0,
        "price_to_book": None,
        "dividend_yield": None,
        "book_value": None,
        "roce": 9.5,
        "roe": None,
        "fundamental_ratios": None,
    }
    upsert_screener_provider_metrics(
        cur,
        stock_id,
        {"ROCE": "99%", "ROE": "12%", "Stock P/E": "30"},
        "screener-src-id",
    )
    row = cur.rows[(stock_id, metric_day)]
    assert row["roce"] == 9.5
    assert row["stock_pe"] == 20.0
    assert row["roe"] == pytest.approx(0.12)


def test_merge_yahoo_daily_fields_preserves_screener_roce_when_yahoo_null():
    merged = merge_yahoo_daily_fields(
        {"market_cap": 1e9, "roce": None, "roe": None, "stock_pe": 20.0},
        {"roce": 0.139, "roe": 0.05, "stock_pe": None},
    )
    assert merged["roce"] == 0.139
    assert merged["roe"] == 0.05
    assert merged["market_cap"] == 1e9
    assert merged["stock_pe"] == 20.0


def test_screener_upsert_then_yahoo_sync_keeps_roce_on_new_metric_date(monkeypatch):
    """Regression: Yahoo null ROCE must not erase Screener-filled latest row after date moves."""
    from unittest.mock import MagicMock
    from uuid import UUID

    import pandas as pd

    stock_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    day1 = date(2024, 5, 1)
    day2 = date(2024, 5, 15)
    long = pd.DataFrame({"date": [day2], "close": [101.0]})

    class _Store:
        def __init__(self) -> None:
            self.rows: dict[tuple, dict] = {}
            self._prior_fetch = False
        def execute(self, sql, params=None) -> None:
            text = " ".join(sql.split())
            if "SELECT market_cap" in text and "ORDER BY metric_date DESC" in text:
                self._prior_fetch = True
                return
            if "INSERT INTO market_data.stock_daily_metrics" in text and params:
                stock_id_p, metric_date = params[0], params[1]
                key = (stock_id_p, metric_date)
                self.rows[key] = {
                    "stock_id": stock_id_p,
                    "metric_date": metric_date,
                    "market_cap": params[2],
                    "stock_pe": params[3],
                    "price_to_book": params[4],
                    "dividend_yield": params[5],
                    "book_value": params[6],
                    "roce": params[7],
                    "roe": params[8],
                    "fundamental_ratios": (
                        params[-1].adapted if hasattr(params[-1], "adapted") else params[-1]
                    ),
                }
                for old in [k for k in self.rows if k[0] == stock_id_p and k[1] != metric_date]:
                    del self.rows[old]
                return
            if "DELETE FROM market_data.stock_daily_metrics" in text and params:
                sid, keep = params
                for key in [k for k in self.rows if k[0] == sid and k[1] != keep]:
                    del self.rows[key]

        def fetchone(self):
            if not self._prior_fetch:
                return None
            self._prior_fetch = False
            if not self.rows:
                return None
            key = max(self.rows, key=lambda item: item[1])
            row = self.rows[key]
            return (
                row.get("market_cap"),
                row.get("stock_pe"),
                row.get("price_to_book"),
                row.get("dividend_yield"),
                row.get("book_value"),
                row.get("roce"),
                row.get("roe"),
                row.get("fundamental_ratios"),
            )

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    store = _Store()
    store.rows[(stock_id, day1)] = {
        "stock_id": stock_id,
        "metric_date": day1,
        "market_cap": None,
        "stock_pe": None,
        "price_to_book": None,
        "dividend_yield": None,
        "book_value": None,
        "roce": 0.139,
        "roe": 0.0561,
        "fundamental_ratios": {"provider_metric_sources": {"roce": "screener"}},
    }

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return store

        def commit(self):
            return None

    yahoo_info = {"marketCap": 500_000_000_000, "trailingPE": 18.5}
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        MagicMock(Ticker=lambda _symbol: MagicMock(info=yahoo_info)),
    )
    monkeypatch.setattr(stock_sync, "_connect", lambda *a, **k: _Conn())
    monkeypatch.setattr(stock_sync, "_run_writable", lambda op, **k: op())
    monkeypatch.setattr(stock_sync, "_source_id", lambda _cur, _name: stock_id)

    def prices(_cur, _symbol):
        return stock_id, long

    monkeypatch.setattr(stock_sync, "_prices", prices)

    result = stock_sync.sync_daily_metrics("AFCONS", force=True)
    only = next(iter(store.rows.values()))
    assert result["status"] == "completed"
    assert only["metric_date"] == day2
    assert only["roce"] == pytest.approx(0.139)
    assert only["market_cap"] == 500_000_000_000
    assert len([k for k in store.rows if k[0] == stock_id]) == 1


def test_yahoo_daily_metric_fields_null_bad_conversions_instead_of_raising():
    fields = yahoo_daily_metric_fields(
        {
            "marketCap": "not-a-number",
            "enterpriseValue": float("nan"),
            "ebitda": float("inf"),
            "totalDebt": object(),
            "totalCash": 10,
            "dividendYield": math.nan,
            "trailingPE": "12.5",
        }
    )
    assert fields["market_cap"] is None
    assert fields["enterprise_value"] is None
    assert fields["ebitda_ttm"] is None
    assert fields["net_debt"] is None
    assert fields["dividend_yield"] is None
    assert fields["stock_pe"] == 12.5
    assert fields["peg"] is None
