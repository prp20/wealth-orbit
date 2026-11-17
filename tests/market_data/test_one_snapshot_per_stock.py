"""One latest snapshot per stock — technicals and daily_metrics must not accumulate by date."""
from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data import sync as stock_sync
from backend.market_data.latest_snapshot import (
    prune_non_latest_metric_dates,
    prune_non_latest_technical_dates,
)

_STOCK_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _indicator_rows_for_date(trading_date: date, n_macd: int = 3) -> pd.DataFrame:
    """Minimal fabricated latest-day rows resembling calculate_indicators output."""
    base = {
        "date": trading_date,
        "indicator_period": 20,
        "component": "VALUE",
        "parameters": '{"period": 20}',
        "value": 1.0,
    }
    rows = [
        {**base, "indicator_code": "SMA"},
        {**base, "indicator_code": "EMA"},
        {**base, "indicator_code": "RSI", "indicator_period": 14, "parameters": '{"period": 14}'},
        {**base, "indicator_code": "BB", "component": "MID"},
        {**base, "indicator_code": "ATR", "indicator_period": 14, "parameters": '{"period": 14}'},
    ]
    # MACD emits line / signal / histogram components at the same date.
    for comp in ("LINE", "SIGNAL", "HIST")[:n_macd]:
        rows.append(
            {
                **base,
                "indicator_code": "MACD",
                "indicator_period": 0,
                "component": comp,
                "parameters": '{"fast": 12, "slow": 26, "signal": 9}',
            }
        )
    return pd.DataFrame(rows)


class _TechnicalSnapshotStore:
    """In-memory stand-in for stock_technical_indicators PK + upsert semantics."""

    def __init__(self) -> None:
        self.rows: dict[tuple, dict] = {}

    @staticmethod
    def _key(stock_id, trading_date, code, period, component, params) -> tuple:
        if isinstance(params, dict):
            params = json.dumps(params, sort_keys=True, separators=(",", ":"))
        return (stock_id, trading_date, code, period, component, params)

    def upsert_execute_values(self, _cur, _sql, values, **kwargs) -> None:
        for row in values:
            stock_id, trading_date, code, period, component, params, value, status = row[:8]
            _calc_version = row[8] if len(row) > 8 else None
            key = self._key(stock_id, trading_date, code, period, component, params)
            self.rows[key] = {
                "stock_id": stock_id,
                "trading_date": trading_date,
                "indicator_code": code,
                "value": value,
                "calculation_status": status,
            }

    def distinct_dates(self, stock_id) -> set[date]:
        return {r["trading_date"] for r in self.rows.values() if r["stock_id"] == stock_id}

    def count(self, stock_id) -> int:
        return sum(1 for r in self.rows.values() if r["stock_id"] == stock_id)


class _PruneCursor:
    def __init__(self, store: _TechnicalSnapshotStore) -> None:
        self.store = store
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None) -> None:
        if "stock_technical_indicators" in sql and params:
            stock_id, keep = params
            removed = 0
            for key, row in list(self.store.rows.items()):
                if row["stock_id"] == stock_id and row["trading_date"] != keep:
                    del self.store.rows[key]
                    removed += 1
            self.rowcount = removed


def test_two_technical_syncs_different_dates_do_not_accumulate_history():
    store = _TechnicalSnapshotStore()
    day1 = date(2024, 6, 1)
    day2 = date(2024, 6, 10)
    rows_day1 = _indicator_rows_for_date(day1)
    rows_day2 = _indicator_rows_for_date(day2)
    expected_keys = len(rows_day1)

    with patch(
        "backend.market_data.sync.execute_values",
        side_effect=store.upsert_execute_values,
    ):
        n1 = stock_sync._persist_latest_technicals(_PruneCursor(store), _STOCK_ID, day1, rows_day1)
        assert n1 == expected_keys
        assert store.count(_STOCK_ID) == expected_keys
        assert store.distinct_dates(_STOCK_ID) == {day1}

        n2 = stock_sync._persist_latest_technicals(_PruneCursor(store), _STOCK_ID, day2, rows_day2)
        assert n2 == expected_keys
        assert store.count(_STOCK_ID) == expected_keys
        assert store.distinct_dates(_STOCK_ID) == {day2}


def test_prune_non_latest_technical_dates_removes_only_other_dates():
    store = _TechnicalSnapshotStore()
    store.upsert_execute_values(
        None,
        "",
        [
            (_STOCK_ID, date(2024, 1, 1), "SMA", 20, "VALUE", "{}", 1.0, "CURRENT"),
            (_STOCK_ID, date(2024, 1, 2), "SMA", 20, "VALUE", "{}", 2.0, "CURRENT"),
            (_STOCK_ID, date(2024, 1, 2), "RSI", 14, "VALUE", "{}", 3.0, "CURRENT"),
        ],
    )
    cur = _PruneCursor(store)
    deleted = prune_non_latest_technical_dates(cur, _STOCK_ID, date(2024, 1, 2))
    assert deleted == 1
    assert store.distinct_dates(_STOCK_ID) == {date(2024, 1, 2)}
    assert store.count(_STOCK_ID) == 2


class _DailyMetricsStore:
    """In-memory stand-in for stock_daily_metrics PK + upsert semantics."""

    def __init__(self) -> None:
        self.rows: dict[tuple, dict] = {}

    def distinct_dates(self, stock_id) -> set[date]:
        return {key[1] for key in self.rows if key[0] == stock_id}

    def count(self, stock_id) -> int:
        return sum(1 for key in self.rows if key[0] == stock_id)


class _DailyMetricsCursor:
    def __init__(self, store: _DailyMetricsStore) -> None:
        self.store = store
        self.rowcount = 0
        self._bag_fetch_stock = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None) -> None:
        text = " ".join(sql.split())
        if (
            "SELECT fundamental_ratios" in text
            and "stock_daily_metrics" in text
            and params
        ):
            self._bag_fetch_stock = params[0]
            return
        if "INSERT INTO market_data.stock_daily_metrics" in text and params:
            stock_id, metric_date = params[0], params[1]
            bag_param = params[-1]
            bag_val = None
            if bag_param is not None:
                bag_val = bag_param.adapted if hasattr(bag_param, "adapted") else bag_param
            key = (stock_id, metric_date)
            existing = self.store.rows.get(key)
            if existing:
                if bag_val is not None:
                    existing["fundamental_ratios"] = bag_val
                else:
                    pass  # COALESCE keeps prior bag
            else:
                self.store.rows[key] = {
                    "stock_id": stock_id,
                    "metric_date": metric_date,
                    "fundamental_ratios": bag_val,
                }
            return
        if "DELETE FROM market_data.stock_daily_metrics" in text and params:
            stock_id, keep = params
            removed = 0
            for key in list(self.store.rows):
                if key[0] == stock_id and key[1] != keep:
                    del self.store.rows[key]
                    removed += 1
            self.rowcount = removed

    def fetchone(self):
        if self._bag_fetch_stock is not None:
            stock_id = self._bag_fetch_stock
            self._bag_fetch_stock = None
            candidates = [
                (row["metric_date"], row["fundamental_ratios"])
                for row in self.store.rows.values()
                if row["stock_id"] == stock_id and row.get("fundamental_ratios") is not None
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda item: item[0], reverse=True)
            return (candidates[0][1],)
        return None


class _MetricsCursor:
    def __init__(self) -> None:
        self.rows: list[tuple] = []
        self.rowcount = 0

    def execute(self, sql, params=None) -> None:
        if "DELETE FROM market_data.stock_daily_metrics" in sql and params:
            stock_id, keep = params
            before = len(self.rows)
            self.rows = [r for r in self.rows if not (r[0] == stock_id and r[1] != keep)]
            self.rowcount = before - len(self.rows)
        elif "INSERT" in sql:
            self.rows.append(params)


def test_prune_non_latest_metric_dates_keeps_one_row():
    cur = _MetricsCursor()
    cur.rows = [
        (_STOCK_ID, date(2024, 3, 1)),
        (_STOCK_ID, date(2024, 6, 1)),
    ]
    deleted = prune_non_latest_metric_dates(cur, _STOCK_ID, date(2024, 6, 1))
    assert deleted == 1
    assert cur.rows == [(_STOCK_ID, date(2024, 6, 1))]


def test_sync_technical_advances_as_of_replaces_snapshot(monkeypatch):
    """End-to-end writer: longer OHLC → new latest date; row cardinality stays fixed."""
    short = pd.DataFrame(
        {
            "date": [date(2024, 1, 1) + timedelta(days=i) for i in range(40)],
            "open": [100.0] * 40,
            "high": [101.0] * 40,
            "low": [99.0] * 40,
            "close": [100.0 + i * 0.1 for i in range(40)],
            "volume": [1000] * 40,
        }
    )
    long = pd.concat(
        [
            short,
            pd.DataFrame(
                {
                    "date": [short["date"].max() + timedelta(days=i) for i in range(1, 6)],
                    "open": [105.0] * 5,
                    "high": [106.0] * 5,
                    "low": [104.0] * 5,
                    "close": [105.5] * 5,
                    "volume": [1100] * 5,
                }
            ),
        ],
        ignore_index=True,
    )
    store = _TechnicalSnapshotStore()
    dates_seen: list[date] = []

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return _PruneCursor(store)

        def commit(self):
            return None

    monkeypatch.setattr(stock_sync, "_connect", lambda *a, **k: _Conn())
    monkeypatch.setattr(stock_sync, "_run_writable", lambda op, **k: op())

    def prices(cur, symbol):
        frame = short if not dates_seen else long
        return _STOCK_ID, frame

    monkeypatch.setattr(stock_sync, "_prices", prices)

    with patch(
        "backend.market_data.sync.execute_values",
        side_effect=store.upsert_execute_values,
    ):
        first = stock_sync.sync_technical_indicators("HDFCBANK", force=True)
        dates_seen.append(1)
        count_after_first = store.count(_STOCK_ID)
        first_date = store.distinct_dates(_STOCK_ID)

        second = stock_sync.sync_technical_indicators("HDFCBANK", force=True)
        count_after_second = store.count(_STOCK_ID)
        second_date = store.distinct_dates(_STOCK_ID)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first_date != second_date
    assert count_after_second == count_after_first
    assert len(second_date) == 1


def test_two_daily_metrics_syncs_different_dates_do_not_accumulate_history(monkeypatch):
    """Yahoo as-of advances; stock_daily_metrics stays one row per stock."""
    short = pd.DataFrame(
        {
            "date": [date(2024, 2, 1) + timedelta(days=i) for i in range(25)],
            "open": [100.0] * 25,
            "high": [101.0] * 25,
            "low": [99.0] * 25,
            "close": [100.0] * 25,
            "volume": [1000] * 25,
        }
    )
    long = pd.concat(
        [
            short,
            pd.DataFrame(
                {
                    "date": [short["date"].max() + timedelta(days=i) for i in range(1, 8)],
                    "open": [102.0] * 7,
                    "high": [103.0] * 7,
                    "low": [101.0] * 7,
                    "close": [102.5] * 7,
                    "volume": [1200] * 7,
                }
            ),
        ],
        ignore_index=True,
    )
    store = _DailyMetricsStore()
    calls = 0

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return _DailyMetricsCursor(store)

        def commit(self):
            return None

    yahoo_info = {
        "marketCap": 500_000_000_000,
        "trailingPE": 18.5,
        "priceToBook": 2.1,
        "totalDebt": 1000,
        "totalCash": 500,
    }
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        MagicMock(Ticker=lambda _symbol: MagicMock(info=yahoo_info)),
    )
    monkeypatch.setattr(stock_sync, "_connect", lambda *a, **k: _Conn())
    monkeypatch.setattr(stock_sync, "_run_writable", lambda op, **k: op())
    monkeypatch.setattr(
        stock_sync,
        "_source_id",
        lambda _cur, _name: uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )

    def prices(_cur, _symbol):
        nonlocal calls
        calls += 1
        frame = short if calls == 1 else long
        return _STOCK_ID, frame

    monkeypatch.setattr(stock_sync, "_prices", prices)

    first = stock_sync.sync_daily_metrics("HDFCBANK", force=True)
    first_date = store.distinct_dates(_STOCK_ID)
    count_after_first = store.count(_STOCK_ID)

    # Simulate a prior fundamentals bag on the latest row before as-of moves again.
    only_key = next(k for k in store.rows if k[0] == _STOCK_ID)
    store.rows[only_key]["fundamental_ratios"] = {"ratios": {"ROE": 22.0}, "as_of": "2024-03-31"}

    second = stock_sync.sync_daily_metrics("HDFCBANK", force=True)
    second_date = store.distinct_dates(_STOCK_ID)
    count_after_second = store.count(_STOCK_ID)
    only_row = next(row for row in store.rows.values() if row["stock_id"] == _STOCK_ID)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert first_date != second_date
    assert len(first_date) == 1
    assert len(second_date) == 1
    assert count_after_first == 1
    assert count_after_second == 1
    assert only_row["fundamental_ratios"]["ratios"]["ROE"] == 22.0
