"""Persistent market sync queue with terminal status and safe transient retries."""
from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

load_dotenv()
logger = logging.getLogger("wealth_orbit.sync")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="market-sync")

MAX_TRANSIENT_ATTEMPTS = 3
_TRANSIENT_MARKERS = (
    "timed out",
    "timeout",
    "connection reset",
    "connection refused",
    "temporary failure",
    "temporarily unavailable",
    "getaddrinfo failed",
    "name or service not known",
    "no such host is known",
    "nodename nor servname",
    "ssl connection failed",
    "ssl syscall",
    "network is unreachable",
    "broken pipe",
)
_PERMANENT_PREFIXES = ("yahoo_", "screener_")


def _db():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)


def is_transient_sync_failure(exc: BaseException) -> bool:
    """Allowlist timeouts / connection blips; never retry validation or permanent provider tokens."""
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False
    text = str(exc).lower().strip()
    if any(text.startswith(prefix) for prefix in _PERMANENT_PREFIXES):
        # Opaque provider tokens are permanent for 1.4 (yahoo_*/screener_*).
        return False
    if isinstance(exc, (TimeoutError, ConnectionError, ConnectionResetError, BrokenPipeError)):
        return True
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def opaque_sync_error(exc: BaseException) -> str:
    """Short last_error with no password / URL material."""
    text = str(exc).strip()
    lower = text.lower()
    if any(lower.startswith(prefix) for prefix in _PERMANENT_PREFIXES) and "://" not in text and len(text) < 120:
        return text.split("\n", 1)[0][:120]
    if "password authentication failed" in lower or "authentication failed" in lower:
        return "authentication failed"
    if "timed out" in lower or "timeout" in lower:
        return "connection timed out"
    if any(
        token in lower
        for token in (
            "could not translate host",
            "name or service not known",
            "nodename nor servname",
            "getaddrinfo failed",
            "no such host is known",
            "temporary failure in name resolution",
            "unknown host",
        )
    ):
        return "host not found"
    if "connection refused" in lower:
        return "connection refused"
    if "connection reset" in lower:
        return "connection reset"
    if "ssl" in lower:
        return "ssl connection failed"
    if "://" in text or "password" in lower or "@" in text:
        return "connection failed"
    # Keep short soft-fail reasons; clamp length.
    cleaned = text.split("\n", 1)[0].strip()
    return cleaned[:160] if cleaned else "sync failed"


def enqueue(entity_type, entity_key, sync_type, force, work):
    with _db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as q:
            # Force mode changes fetch semantics, not the identity of a running job.
            # Do not allow a force and non-force sync for the same entity/type to race.
            q.execute(
                "SELECT * FROM market_data.sync_jobs WHERE entity_type=%s AND entity_key=%s AND sync_type=%s AND status IN ('QUEUED','RUNNING') ORDER BY queued_at LIMIT 1",
                (entity_type, entity_key, sync_type),
            )
            old = q.fetchone()
            if old:
                return dict(old), False
            q.execute(
                "INSERT INTO market_data.sync_jobs(job_id,entity_type,entity_key,sync_type,force_sync) VALUES(%s,%s,%s,%s,%s) RETURNING *",
                (str(uuid4()), entity_type, entity_key, sync_type, force),
            )
            job = dict(q.fetchone())
    _executor.submit(_run, job["job_id"], work)
    return job, True


def _job_meta(job_id: str) -> dict:
    row = get_job(job_id)
    if not row:
        return {"job_id": job_id, "entity_type": None, "entity_key": None, "sync_type": None}
    return {
        "job_id": job_id,
        "entity_type": row.get("entity_type"),
        "entity_key": row.get("entity_key"),
        "sync_type": row.get("sync_type"),
    }


def _mark_running(job_id: str) -> None:
    with _db() as c:
        with c.cursor() as q:
            q.execute(
                "UPDATE market_data.sync_jobs SET status='RUNNING',started_at=COALESCE(started_at, now()),progress_percent=10,updated_at=now() WHERE job_id=%s",
                (job_id,),
            )


def _mark_succeeded(job_id: str, result) -> None:
    with _db() as c:
        with c.cursor() as q:
            q.execute(
                "UPDATE market_data.sync_jobs SET status='SUCCEEDED',progress_percent=100,completed_at=now(),result=%s,last_error=NULL,updated_at=now() WHERE job_id=%s",
                (json.dumps(result, default=str), job_id),
            )


def _mark_failed(job_id: str, reason: str) -> None:
    with _db() as c:
        with c.cursor() as q:
            q.execute(
                "UPDATE market_data.sync_jobs SET status='FAILED',progress_percent=100,completed_at=now(),last_error=%s,updated_at=now() WHERE job_id=%s",
                (reason, job_id),
            )


def _run(job_id, work):
    meta = _job_meta(job_id)
    logger.info(
        "sync started job_id=%s entity_type=%s entity_key=%s sync_type=%s",
        job_id,
        meta.get("entity_type"),
        meta.get("entity_key"),
        meta.get("sync_type"),
    )
    last_reason = "sync failed"
    for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
        try:
            _mark_running(job_id)
            result = work()
            soft_failed = isinstance(result, dict) and str(result.get("status", "")).lower() in {"failed", "error"}
            if soft_failed:
                reason = result.get("reason") or result.get("error") or "Sync reported failed status"
                raise RuntimeError(reason)
            logger.info("sync succeeded job_id=%s attempt=%s", job_id, attempt)
            _mark_succeeded(job_id, result)
            return
        except Exception as exc:
            last_reason = opaque_sync_error(exc)
            transient = is_transient_sync_failure(exc)
            logger.warning(
                "sync failure job_id=%s entity_type=%s entity_key=%s sync_type=%s attempt=%s transient=%s reason=%s",
                job_id,
                meta.get("entity_type"),
                meta.get("entity_key"),
                meta.get("sync_type"),
                attempt,
                transient,
                last_reason,
            )
            if transient and attempt < MAX_TRANSIENT_ATTEMPTS:
                time.sleep(min(0.5 * attempt, 1.5))
                continue
            break
    try:
        _mark_failed(job_id, last_reason)
    except Exception:
        logger.exception("failed to persist terminal failure job_id=%s", job_id)


def get_job(job_id):
    with _db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as q:
            q.execute("SELECT * FROM market_data.sync_jobs WHERE job_id=%s", (job_id,))
            return q.fetchone()


def latest_job(entity_type, entity_key, sync_type=None):
    """Return the most recent sync job for an entity, optionally filtered by sync_type."""
    with _db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as q:
            if sync_type:
                q.execute(
                    "SELECT * FROM market_data.sync_jobs WHERE entity_type=%s AND entity_key=%s AND sync_type=%s ORDER BY queued_at DESC LIMIT 1",
                    (entity_type, entity_key, sync_type),
                )
            else:
                q.execute(
                    "SELECT * FROM market_data.sync_jobs WHERE entity_type=%s AND entity_key=%s ORDER BY queued_at DESC LIMIT 1",
                    (entity_type, entity_key),
                )
            return q.fetchone()


def latest_jobs_by_kind(entity_type, entity_key, sync_types):
    """Map each sync_type to its latest job summary (or None)."""
    result = {}
    with _db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as q:
            for sync_type in sync_types:
                q.execute(
                    "SELECT job_id, status, completed_at, started_at, queued_at, last_error, progress_percent FROM market_data.sync_jobs WHERE entity_type=%s AND entity_key=%s AND sync_type=%s ORDER BY queued_at DESC LIMIT 1",
                    (entity_type, entity_key, sync_type),
                )
                row = q.fetchone()
                result[sync_type.lower()] = dict(row) if row else None
    return result


def list_jobs(include_terminal: bool = False, limit: int = 25):
    limit = max(1, min(int(limit or 25), 100))
    with _db() as c:
        with c.cursor() as q:
            q.execute(
                "UPDATE market_data.sync_jobs SET status='FAILED',completed_at=now(),last_error='Recovered stale queued/running job after worker restart',updated_at=now() WHERE (status='QUEUED' AND queued_at < now() - interval '10 minutes') OR (status='RUNNING' AND started_at < now() - interval '10 minutes')"
            )
        with c.cursor(cursor_factory=RealDictCursor) as q:
            if include_terminal:
                q.execute(
                    "SELECT * FROM market_data.sync_jobs ORDER BY queued_at DESC LIMIT %s",
                    (limit,),
                )
            else:
                q.execute(
                    "SELECT * FROM market_data.sync_jobs WHERE status IN ('QUEUED','RUNNING') ORDER BY queued_at DESC LIMIT %s",
                    (limit,),
                )
            return q.fetchall()
