"""Persistent market sync queue with terminal status and safe transient retries."""
from __future__ import annotations

import json
import logging
import os
import re
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
_PERMANENT_TOKEN_RE = re.compile(r"(?:yahoo_|screener_)[a-z0-9_]+", re.IGNORECASE)


class SoftSyncFailure(RuntimeError):
    """Provider returned a failed status dict. Never retry."""


def _db():
    return psycopg2.connect(os.environ["DATABASE_URL"], connect_timeout=15)


def _exception_chain(exc: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        nxt = current.__cause__ if current.__cause__ is not None else current.__context__
        current = nxt if isinstance(nxt, BaseException) else None
    return chain


def _permanent_provider_token(text: str) -> str | None:
    match = _PERMANENT_TOKEN_RE.search(text or "")
    return match.group(0) if match else None


def is_transient_sync_failure(exc: BaseException) -> bool:
    """Allowlist timeouts / connection blips; never retry validation or permanent provider tokens."""
    if isinstance(exc, SoftSyncFailure):
        return False
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return False
    for item in _exception_chain(exc):
        if isinstance(item, SoftSyncFailure):
            return False
        if isinstance(item, (ValueError, TypeError, KeyError)):
            return False
        text = str(item)
        if _permanent_provider_token(text):
            return False
    for item in _exception_chain(exc):
        if isinstance(item, (TimeoutError, ConnectionError, ConnectionResetError, BrokenPipeError)):
            return True
        text = str(item).lower()
        if any(marker in text for marker in _TRANSIENT_MARKERS):
            return True
    return False


def opaque_sync_error(exc: BaseException) -> str:
    """Short last_error with no password / URL material."""
    for item in _exception_chain(exc):
        token = _permanent_provider_token(str(item))
        if token and "://" not in str(item):
            return token[:120]
    text = str(exc).strip()
    lower = text.lower()
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
    cleaned = text.split("\n", 1)[0].strip()
    return cleaned[:160] if cleaned else "sync failed"


def enqueue(entity_type, entity_key, sync_type, force, work):
    recover_stale_jobs()
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
    meta = {"job_id": job_id, "entity_type": None, "entity_key": None, "sync_type": None}
    try:
        meta = _job_meta(job_id)
        logger.info(
            "sync started job_id=%s entity_type=%s entity_key=%s sync_type=%s",
            job_id,
            meta.get("entity_type"),
            meta.get("entity_key"),
            meta.get("sync_type"),
        )
    except Exception as exc:
        reason = opaque_sync_error(exc)
        logger.warning("sync startup failed job_id=%s reason=%s", job_id, reason)
        try:
            _mark_failed(job_id, reason)
        except Exception:
            logger.exception("failed to persist terminal failure job_id=%s", job_id)
        return

    last_reason = "sync failed"
    for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
        try:
            _mark_running(job_id)
            result = work()
            soft_failed = isinstance(result, dict) and str(result.get("status", "")).lower() in {"failed", "error"}
            if soft_failed:
                reason = result.get("reason") or result.get("error") or "Sync reported failed status"
                raise SoftSyncFailure(reason)
        except SoftSyncFailure as exc:
            last_reason = opaque_sync_error(exc)
            logger.warning(
                "sync soft-failed job_id=%s entity_type=%s entity_key=%s sync_type=%s attempt=%s reason=%s",
                job_id,
                meta.get("entity_type"),
                meta.get("entity_key"),
                meta.get("sync_type"),
                attempt,
                last_reason,
            )
            break
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

        # work() completed successfully — persist is never part of the work retry loop.
        try:
            logger.info("sync succeeded job_id=%s attempt=%s", job_id, attempt)
            _mark_succeeded(job_id, result)
            return
        except Exception as exc:
            last_reason = opaque_sync_error(exc)
            logger.warning(
                "sync persist-succeeded failed job_id=%s entity_type=%s entity_key=%s sync_type=%s reason=%s",
                job_id,
                meta.get("entity_type"),
                meta.get("entity_key"),
                meta.get("sync_type"),
                last_reason,
            )
            try:
                _mark_failed(job_id, last_reason)
            except Exception:
                logger.exception("failed to persist terminal failure job_id=%s", job_id)
            return

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


def recover_stale_jobs() -> int:
    """Mark abandoned QUEUED/RUNNING jobs FAILED. Call from writers (enqueue), not Home reads."""
    with _db() as c:
        with c.cursor() as q:
            q.execute(
                """UPDATE market_data.sync_jobs
                   SET status='FAILED', completed_at=now(),
                       last_error='Recovered stale queued/running job after worker restart',
                       updated_at=now()
                   WHERE (status='QUEUED' AND queued_at < now() - interval '10 minutes')
                      OR (status='RUNNING' AND started_at < now() - interval '10 minutes')"""
            )
            return q.rowcount or 0


def list_jobs(include_terminal: bool = False, limit: int | None = 25):
    """Read sync jobs. Does not mutate job status (stale recovery runs on enqueue)."""
    with _db() as c:
        with c.cursor(cursor_factory=RealDictCursor) as q:
            if include_terminal:
                capped = max(1, min(int(limit or 25), 100))
                q.execute(
                    "SELECT * FROM market_data.sync_jobs ORDER BY queued_at DESC LIMIT %s",
                    (capped,),
                )
            else:
                # Active-only: do not LIMIT so live jobs are not truncated under load.
                q.execute(
                    "SELECT * FROM market_data.sync_jobs WHERE status IN ('QUEUED','RUNNING') ORDER BY queued_at DESC"
                )
            return q.fetchall()
