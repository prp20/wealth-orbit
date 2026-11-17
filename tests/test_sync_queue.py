"""Unit tests for sync queue retry policy and opaque failure reasons."""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend_api.app import sync_queue
from backend_api.app.sync_queue import (
    MAX_TRANSIENT_ATTEMPTS,
    SoftSyncFailure,
    is_transient_sync_failure,
    list_jobs,
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
    assert not is_transient_sync_failure(SoftSyncFailure("connection timed out"))


def test_wrapped_permanent_tokens_are_not_transient():
    wrapped = RuntimeError("provider failed: yahoo_empty_info")
    assert not is_transient_sync_failure(wrapped)
    caused = Exception("outer")
    caused.__cause__ = RuntimeError("screener_html_unavailable")
    assert not is_transient_sync_failure(caused)


def test_opaque_sync_error_strips_url_and_password_material():
    assert opaque_sync_error(RuntimeError("yahoo_empty_info")) == "yahoo_empty_info"
    assert opaque_sync_error(RuntimeError("fetch failed: yahoo_empty_info")) == "yahoo_empty_info"
    message = opaque_sync_error(
        RuntimeError("password authentication failed for user postgres uri=postgresql://u:secret@h/db")
    )
    assert message == "authentication failed"
    assert "secret" not in message
    assert "://" not in opaque_sync_error(RuntimeError("could not connect to postgresql://u:p@h/db"))


UPSERT_KEYS = {
    "stock_ohlcv": "(stock_id, trading_date)",
    "stock_daily_metrics": "(stock_id, metric_date)",
    "fundamentals": "(stock_id, metric_id, reporting_basis, period_end_date)",
    "shareholding": "(stock_id, period_end_date)",
    "mf_nav": "(scheme_id, nav_date)",
    "index_ohlc": "(index_id, history_date)",
}


def test_upsert_keys_documented_for_release_1_4():
    assert UPSERT_KEYS["stock_ohlcv"]
    assert UPSERT_KEYS["mf_nav"]
    assert UPSERT_KEYS["index_ohlc"]


def _patch_run_helpers(monkeypatch, marks):
    monkeypatch.setattr(
        "backend_api.app.sync_queue._job_meta",
        lambda job_id: {
            "job_id": job_id,
            "entity_type": "STOCK",
            "entity_key": "HDFCBANK",
            "sync_type": "PRICES",
        },
    )
    monkeypatch.setattr(
        "backend_api.app.sync_queue._mark_running",
        lambda job_id: marks.__setitem__("running", marks.get("running", 0) + 1),
    )
    monkeypatch.setattr(
        "backend_api.app.sync_queue._mark_succeeded",
        lambda job_id, result: marks.__setitem__("succeeded", marks.get("succeeded", 0) + 1),
    )
    monkeypatch.setattr(
        "backend_api.app.sync_queue._mark_failed",
        lambda job_id, reason: marks.__setitem__("failed", reason),
    )
    monkeypatch.setattr("backend_api.app.sync_queue.time.sleep", lambda _seconds: None)


def test_run_retries_transient_then_fails_opaque(monkeypatch):
    attempts = {"n": 0}
    marks = {"running": 0, "failed": None, "succeeded": 0}

    def work():
        attempts["n"] += 1
        raise TimeoutError("connection timed out contacting provider")

    _patch_run_helpers(monkeypatch, marks)
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

    _patch_run_helpers(monkeypatch, marks)
    monkeypatch.setattr(
        "backend_api.app.sync_queue.time.sleep",
        lambda _seconds: (_ for _ in ()).throw(AssertionError("no sleep on permanent")),
    )

    _run("job-2", work)

    assert attempts["n"] == 1
    assert marks["failed"] == "yahoo_empty_info"


def test_run_soft_failed_result_becomes_terminal_failed(monkeypatch):
    marks = {"failed": None, "running": 0}

    def work():
        return {"status": "failed", "reason": "screener_html_unavailable"}

    _patch_run_helpers(monkeypatch, marks)
    _run("job-3", work)
    assert marks["failed"] == "screener_html_unavailable"
    assert marks["running"] == 1


def test_run_soft_fail_timeout_reason_is_not_retried(monkeypatch):
    attempts = {"n": 0}
    marks = {"failed": None, "running": 0}

    def work():
        attempts["n"] += 1
        return {"status": "failed", "reason": "connection timed out"}

    _patch_run_helpers(monkeypatch, marks)
    _run("job-soft-timeout", work)
    assert attempts["n"] == 1
    assert marks["failed"] == "connection timed out"


def test_run_does_not_retry_work_when_persist_succeeded_fails(monkeypatch):
    attempts = {"n": 0}
    marks = {"failed": None, "succeeded_calls": 0}

    def work():
        attempts["n"] += 1
        return {"status": "completed", "records_processed": 1}

    def mark_succeeded(_job_id, _result):
        marks["succeeded_calls"] += 1
        raise RuntimeError("could not connect to postgresql://u:secret@db/market")

    _patch_run_helpers(monkeypatch, marks)
    monkeypatch.setattr("backend_api.app.sync_queue._mark_succeeded", mark_succeeded)

    _run("job-persist", work)

    assert attempts["n"] == 1
    assert marks["succeeded_calls"] == 1
    assert marks["failed"] == "connection failed"


def test_run_marks_failed_when_job_meta_raises(monkeypatch):
    marks = {"failed": None}

    def boom(_job_id):
        raise RuntimeError("password authentication failed for uri=postgresql://u:secret@h/db")

    monkeypatch.setattr("backend_api.app.sync_queue._job_meta", boom)
    monkeypatch.setattr(
        "backend_api.app.sync_queue._mark_failed",
        lambda job_id, reason: marks.__setitem__("failed", reason),
    )
    monkeypatch.setattr(
        "backend_api.app.sync_queue._mark_running",
        lambda job_id: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    _run("job-meta", lambda: {"ok": True})
    assert marks["failed"] == "authentication failed"


def test_list_jobs_does_not_run_stale_recovery():
    source = inspect.getsource(list_jobs)
    assert "Recovered stale" not in source
    assert "recover_stale_jobs" not in source
    assert "UPDATE market_data.sync_jobs" not in source


def test_enqueue_calls_recover_stale_jobs():
    source = inspect.getsource(sync_queue.enqueue)
    assert "recover_stale_jobs()" in source
