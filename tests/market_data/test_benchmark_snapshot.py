import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend import reference_service
from backend.reference_service import benchmark_snapshot


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_snapshot_change_uses_the_previous_close_and_keeps_request_order(monkeypatch):
    monkeypatch.setattr(
        reference_service,
        "_index_history_query",
        lambda *_args, **_kwargs: _frame(
            [
                {
                    "index_code": "NIFTY50",
                    "index_name": "Nifty 50",
                    "close": 110.0,
                    "previous_close": 100.0,
                    "as_of": "2026-11-05",
                },
                {
                    "index_code": "SENSEX",
                    "index_name": "Sensex",
                    "close": 220.0,
                    "previous_close": 200.0,
                    "as_of": "2026-11-05",
                },
            ]
        ),
    )

    rows = benchmark_snapshot(["SENSEX", "NIFTY50"])

    assert [row["index_code"] for row in rows] == ["SENSEX", "NIFTY50"]
    assert rows[1]["change_pct"] == 10.0
    assert rows[0]["change_pct"] == 10.0


def test_snapshot_skips_change_when_previous_close_is_zero(monkeypatch):
    monkeypatch.setattr(
        reference_service,
        "_index_history_query",
        lambda *_args, **_kwargs: _frame(
            [
                {
                    "index_code": "NIFTY50",
                    "index_name": "Nifty 50",
                    "close": 110.0,
                    "previous_close": 0,
                    "as_of": "2026-11-05",
                }
            ]
        ),
    )

    rows = benchmark_snapshot(["NIFTY50"])

    assert len(rows) == 1
    assert rows[0]["close"] == 110.0
    assert rows[0]["change_pct"] is None


def test_snapshot_omits_codes_with_no_rows(monkeypatch):
    monkeypatch.setattr(
        reference_service,
        "_index_history_query",
        lambda *_args, **_kwargs: _frame(
            [
                {
                    "index_code": "NIFTY50",
                    "index_name": "Nifty 50",
                    "close": 110.0,
                    "previous_close": 100.0,
                    "as_of": "2026-11-05",
                }
            ]
        ),
    )

    rows = benchmark_snapshot(["MISSING", "NIFTY50"])

    assert [row["index_code"] for row in rows] == ["NIFTY50"]
