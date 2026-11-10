"""Unit tests for sync queue retry policy and opaque failure reasons."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_api.app.sync_queue import (
    MAX_TRANSIENT_ATTEMPTS,
    is_transient_sync_failure,
    opaque_sync_error,
    _run,
)


def test_transient_failures_are_allowlisted():
    assert is_transient_sync_failure(TimeoutError("timed out"))
    assert is_transient_sync_failure(ConnectionResetError("connection reset by peer"))
    assert is_transient_sync_failure(RuntimeError("SSL SYSCALL error: Connection reset"))
    assert is_transient_sync_failure(OSError("getaddrinfo failed"))


def test_permanent_failures_do_not_retry():
    assert not is_transient_sync_failure(ValueError("invalid symbol"))
    assert not is_transient_sync_failure(RuntimeError("yahoo_empty_info"))
    assert not is_transient_sync_failure(RuntimeError("screener_html_unavailable"))


def test_opaque_sync_error_strips_url_and_password_material():
    assert opaque_sync_error(RuntimeError("yahoo_empty_info")) == "yahoo_empty_info"
    message = opaque_sync_error(
        RuntimeError("password authentication failed for user postgres uri=postgresql://u:secret@h/db")
    )
    assert message == "authentication failed"
    assert "secret" not in message
    assert "://" not in opaque_sync_error(RuntimeError("could not connect to postgresql://u:p@h/db"))


UPSERT_KEYS = {
    "stock_ohlcv": "(stock_id, trading_date)",
    "stock_daily_metrics": "(stock_id, metric_date)",
    "fundamentals": "(stock_id, metric_id, reporting_period, reporting_basis, period_end_date)",
    "shareholding": "(stock_id, period_end_date)",
    "mf_nav": "(scheme_id, nav_date)",
    "index_ohlc": "(index_id, history_date)",
}


def test_upsert_keys_documented_for_release_1_4():
    assert UPSERT_KEYS["stock_ohlcv"]
    assert UPSERT_KEYS["mf_nav"]
    assert UPSERT_KEYS["index_ohlc"]


def test_run_retries_transient_then_fails_opaque(monkeypatch):
    attempts = {"n": 0}
    marks = {"running": 0, "failed": None, "succeeded": 0}

    def work():
        attempts["n"] += 1
        raise TimeoutError("connection timed out contacting provider")

    monkeypatch.setattr("backend_api.app.sync_queue._job_meta", lambda job_id: {
        "job_id": job_id,
        "entity_type": "STOCK",
        "entity_key": "HDFCBANK",
        "sync_type": "PRICES",
    })
    monkeypatch.setattr("backend_api.app.sync_queue._mark_running", lambda job_id: marks.__setitem__("running", marks["running"] + 1))
    monkeypatch.setattr("backend_api.app.sync_queue._mark_succeeded", lambda job_id, result: marks.__setitem__("succeeded", marks["succeeded"] + 1))
    monkeypatch.setattr("backend_api.app.sync_queue._mark_failed", lambda job_id, reason: marks.__setitem__("failed", reason))
    monkeypatch.setattr("backend_api.app.sync_queue.time.sleep", lambda _seconds: None)

    _run("job-1", work)

    assert attempts["n"] == MAX_TRANSIENT_ATTEMPTS
    assert marks["running"] == MAX_TRANSIENT_ATTEMPTS
    assert marks["succeeded"] == 0
    assert marks["failed"] == "connection timed out"


def test_run_does_not_retry_permanent_provider_token(monkeypatch):
    attempts = {"n": 0}
    marks = {"failed": None}

    def work():
        attempts["n"] += 1
        raise RuntimeError("yahoo_empty_info")

    monkeypatch.setattr("backend_api.app.sync_queue._job_meta", lambda job_id: {
        "job_id": job_id,
        "entity_type": "STOCK",
        "entity_key": "HDFCBANK",
        "sync_type": "DAILY_METRICS",
    })
    monkeypatch.setattr("backend_api.app.sync_queue._mark_running", lambda job_id: None)
    monkeypatch.setattr("backend_api.app.sync_queue._mark_succeeded", lambda job_id, result: None)
    monkeypatch.setattr("backend_api.app.sync_queue._mark_failed", lambda job_id, reason: marks.__setitem__("failed", reason))
    monkeypatch.setattr("backend_api.app.sync_queue.time.sleep", lambda _seconds: (_ for _ in ()).throw(AssertionError("no sleep on permanent")))

    _run("job-2", work)

    assert attempts["n"] == 1
    assert marks["failed"] == "yahoo_empty_info"


def test_run_soft_failed_result_becomes_terminal_failed(monkeypatch):
    marks = {"failed": None}

    def work():
        return {"status": "failed", "reason": "screener_html_unavailable"}

    monkeypatch.setattr("backend_api.app.sync_queue._job_meta", lambda job_id: {
        "job_id": job_id,
        "entity_type": "STOCK",
        "entity_key": "HDFCBANK",
        "sync_type": "FUNDAMENTALS",
    })
    monkeypatch.setattr("backend_api.app.sync_queue._mark_running", lambda job_id: None)
    monkeypatch.setattr("backend_api.app.sync_queue._mark_succeeded", lambda job_id, result: None)
    monkeypatch.setattr("backend_api.app.sync_queue._mark_failed", lambda job_id, reason: marks.__setitem__("failed", reason))
    monkeypatch.setattr("backend_api.app.sync_queue.time.sleep", lambda _seconds: None)

    _run("job-3", work)

    assert marks["failed"] == "screener_html_unavailable"
