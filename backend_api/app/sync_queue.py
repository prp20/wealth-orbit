import os, json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import psycopg2
import logging
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
load_dotenv()
logger=logging.getLogger("wealth_orbit.sync")
_executor=ThreadPoolExecutor(max_workers=2,thread_name_prefix='market-sync')
def _db(): return psycopg2.connect(os.environ['DATABASE_URL'],connect_timeout=15)
def enqueue(entity_type,entity_key,sync_type,force,work):
    with _db() as c:
      with c.cursor(cursor_factory=RealDictCursor) as q:
        # Force mode changes fetch semantics, not the identity of a running job.
        # Do not allow a force and non-force sync for the same entity/type to race.
        q.execute("SELECT * FROM market_data.sync_jobs WHERE entity_type=%s AND entity_key=%s AND sync_type=%s AND status IN ('QUEUED','RUNNING') ORDER BY queued_at LIMIT 1",(entity_type,entity_key,sync_type)); old=q.fetchone()
        if old:return dict(old),False
        q.execute("INSERT INTO market_data.sync_jobs(job_id,entity_type,entity_key,sync_type,force_sync) VALUES(%s,%s,%s,%s,%s) RETURNING *",(str(uuid4()),entity_type,entity_key,sync_type,force)); job=dict(q.fetchone())
    _executor.submit(_run,job['job_id'],work); return job,True
def _run(job_id,work):
  try:
    logger.info("sync started job_id=%s", job_id)
    with _db() as c:
      with c.cursor() as q:q.execute("UPDATE market_data.sync_jobs SET status='RUNNING',started_at=now(),progress_percent=10,updated_at=now() WHERE job_id=%s",(job_id,))
    result=work()
    soft_failed = isinstance(result, dict) and str(result.get("status", "")).lower() in {"failed", "error"}
    if soft_failed:
      reason = result.get("reason") or result.get("error") or "Sync reported failed status"
      raise RuntimeError(reason)
    logger.info("sync succeeded job_id=%s", job_id)
    with _db() as c:
      with c.cursor() as q:q.execute("UPDATE market_data.sync_jobs SET status='SUCCEEDED',progress_percent=100,completed_at=now(),result=%s,updated_at=now() WHERE job_id=%s",(json.dumps(result,default=str),job_id))
  except Exception as exc:
    logger.exception("sync failed job_id=%s", job_id)
    try:
      with _db() as c:
        with c.cursor() as q:q.execute("UPDATE market_data.sync_jobs SET status='FAILED',progress_percent=100,completed_at=now(),last_error=%s,updated_at=now() WHERE job_id=%s",(str(exc),job_id))
    except Exception:
      logger.exception("failed to persist terminal failure job_id=%s", job_id)
def get_job(job_id):
  with _db() as c:
    with c.cursor(cursor_factory=RealDictCursor) as q:q.execute("SELECT * FROM market_data.sync_jobs WHERE job_id=%s",(job_id,)); return q.fetchone()

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

def list_jobs(include_terminal: bool = False):
  with _db() as c:
    with c.cursor() as q:q.execute("UPDATE market_data.sync_jobs SET status='FAILED',completed_at=now(),last_error='Recovered stale queued/running job after worker restart',updated_at=now() WHERE (status='QUEUED' AND queued_at < now() - interval '10 minutes') OR (status='RUNNING' AND started_at < now() - interval '10 minutes')")
    with c.cursor(cursor_factory=RealDictCursor) as q:q.execute("SELECT * FROM market_data.sync_jobs %s ORDER BY queued_at DESC" % ("" if include_terminal else "WHERE status IN ('QUEUED','RUNNING')")); return q.fetchall()
