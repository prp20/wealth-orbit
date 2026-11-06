import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend import reference_service
from backend.reference_service import mutual_fund_similar_enriched


def test_similar_funds_match_plan_option_and_source_period(monkeypatch):
    calls: list[str] = []

    def fake_query(sql, _params=()):
        calls.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(reference_service, "mutual_fund_detail", lambda code: {"scheme_code": code})
    monkeypatch.setattr(reference_service, "_query", fake_query)

    assert mutual_fund_similar_enriched("122639") == []
    assert len(calls) == 1
    sql = calls[0]
    peers = sql.split("latest_metrics")[0]
    assert "plan_type IS NOT DISTINCT FROM" in peers
    assert "option_type IS NOT DISTINCT FROM" in peers
    assert "LIMIT 20" in peers
    assert "x.metric_period = (SELECT metric_period FROM source_period)" in sql
    assert "ORDER BY x.scheme_id, x.available DESC, x.as_of_date DESC, CASE" not in sql.split("latest_metrics", 1)[1]


def test_similar_funds_skip_query_when_scheme_is_missing(monkeypatch):
    monkeypatch.setattr(reference_service, "mutual_fund_detail", lambda _code: None)

    def boom(*_args, **_kwargs):
        raise AssertionError("peer query should not run")

    monkeypatch.setattr(reference_service, "_query", boom)
    assert mutual_fund_similar_enriched("missing") == []
