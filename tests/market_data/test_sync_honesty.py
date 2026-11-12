"""Sync-path honesty: opaque failure tokens and dual-basis persistence."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data import sync as stock_sync
from backend import reference_service


def test_sync_daily_metrics_uses_opaque_yahoo_failure_token(monkeypatch):
    class Boom:
        @property
        def info(self):
            raise RuntimeError("cookie=secret host=internal")

    monkeypatch.setitem(sys.modules, "yfinance", MagicMock(Ticker=lambda _symbol: Boom()))
    with pytest.raises(RuntimeError, match=r"Daily metrics sync failed for HDFCBANK: yahoo_info_unavailable") as raised:
        stock_sync.sync_daily_metrics("HDFCBANK")
    assert "cookie" not in str(raised.value)
    assert "secret" not in str(raised.value)


def test_sync_daily_metrics_uses_opaque_empty_info_token(monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "yfinance",
        MagicMock(Ticker=lambda _symbol: MagicMock(info={})),
    )
    with pytest.raises(RuntimeError, match=r"Daily metrics sync failed for HDFCBANK: yahoo_info_empty"):
        stock_sync.sync_daily_metrics("HDFCBANK")


def test_sync_stock_fundamentals_uses_opaque_html_unavailable_token(monkeypatch):
    stock_id = uuid4()

    class FakeCursor:
        def execute(self, sql, params=None):
            self.last_sql = sql
            self.last_params = params

        def fetchone(self):
            if "stock_reference" in getattr(self, "last_sql", ""):
                return (stock_id,)
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

    monkeypatch.setattr(reference_service.psycopg2, "connect", lambda *a, **k: FakeConn())
    monkeypatch.setattr(
        "backend.market_data.providers.screener.fetch_html",
        lambda *a, **k: None,
    )
    with pytest.raises(RuntimeError, match=r"Fundamentals sync failed for HDFCBANK: screener_html_unavailable"):
        reference_service.sync_stock_fundamentals("HDFCBANK")


def test_sync_stock_fundamentals_persists_both_bases_without_clobber(monkeypatch):
    stock_id = uuid4()
    source_id = uuid4()
    inserts = []
    value_sql = []
    metric_ids = {}

    class FakeCursor:
        def __init__(self):
            self.last_sql = ""
            self.last_params = None
            self.rowcount = 0

        def execute(self, sql, params=None):
            self.last_sql = " ".join(sql.split())
            self.last_params = params
            self.rowcount = 0
            if "INSERT INTO market_data.fundamental_metric_reference" in self.last_sql:
                # Single-row path (legacy) or leftover execute_values expansion.
                if params and len(params) >= 2 and not isinstance(params[0], (list, tuple)):
                    metric_ids[params[1]] = params[0]

        def fetchone(self):
            sql = self.last_sql
            if "FROM market_data.stock_reference" in sql:
                return (stock_id,)
            if "FROM market_data.stock_daily_metrics" in sql and "ORDER BY metric_date DESC" in sql:
                return None
            return None

        def fetchall(self):
            if "FROM market_data.fundamental_metric_reference" in self.last_sql:
                return [
                    (code, metric_id, "CF")
                    for code, metric_id in metric_ids.items()
                ]
            # Annual consol statement pull for ratio snapshot — empty is fine for this test.
            return []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def cursor(self):
            return FakeCursor()

        def commit(self):
            return None

    def fake_execute_values(cur, sql, argslist, template=None, page_size=100, fetch=False):
        normalized = " ".join(sql.split())
        if "INSERT INTO market_data.fundamental_metric_reference" in normalized:
            for row in argslist:
                metric_ids[row[1]] = row[0]
            return None
        if (
            "INSERT INTO market_data.stock_annual_fundamental_values" in normalized
            or "INSERT INTO market_data.stock_quarterly_fundamental_values" in normalized
        ):
            inserts.extend(argslist)
            value_sql.append(normalized)
            return None
        return None

    html_by_basis = {
        "CONSOLIDATED": """
            <section id="cash-flow"><table class="data-table">
              <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
              <tbody><tr><td>Cash from Operating Activity</td><td>40</td></tr></tbody>
            </table></section>
            """,
        "STANDALONE": """
            <section id="cash-flow"><table class="data-table">
              <thead><tr><th>Particulars</th><th>Mar 2024</th></tr></thead>
              <tbody><tr><td>Cash from Operating Activity</td><td>35</td></tr></tbody>
            </table></section>
            """,
    }

    def fake_fetch(url, *_args, **_kwargs):
        if "consolidated" in url:
            return html_by_basis["CONSOLIDATED"]
        return html_by_basis["STANDALONE"]

    monkeypatch.setattr(reference_service.psycopg2, "connect", lambda *a, **k: FakeConn())
    monkeypatch.setattr(reference_service, "execute_values", fake_execute_values)
    monkeypatch.setattr("backend.market_data.providers.screener.fetch_html", fake_fetch)
    monkeypatch.setattr(
        "backend.market_data.sources.ensure_data_source",
        lambda _cur, _name: source_id,
    )

    result = reference_service.sync_stock_fundamentals("HDFCBANK")
    assert result["status"] == "completed"
    assert result["fundamental_rows_consolidated"] == 1
    assert result["fundamental_rows_standalone"] == 1
    assert result["basis_warnings"] == []
    # row: stock_id, metric_id, period_start, period_end, reporting_basis, value, source_id
    bases = {row[4] for row in inserts}
    values = {row[4]: row[5] for row in inserts}
    assert bases == {"CONSOLIDATED", "STANDALONE"}
    assert values["CONSOLIDATED"] == 40.0
    assert values["STANDALONE"] == 35.0
    assert all("stock_annual_fundamental_values" in sql for sql in value_sql)
    assert all("ON CONFLICT" in sql for sql in value_sql)
