# Persistent Market Sync Queue Plan

**Goal:** Separate synchronization into independently queueable daily metrics, fundamentals, shareholding history, and technical indicators jobs; persist job state in PostgreSQL; expose progress and queue position; and make force-sync controls unavailable while the matching job is queued or running.

## Design decisions

- Use a single `market_data.sync_jobs` table for stocks and mutual funds rather than four queue tables.
- A job identity is `(entity_type, entity_id, sync_type, force)`; an active partial unique index prevents duplicate `QUEUED`/`RUNNING` jobs.
- The in-process executor remains the V1 worker, but the database is the source of truth. This allows a future Celery/RQ worker to consume the same records.
- Terminal jobs remain queryable for audit/history; a cleanup policy can archive old successes later.
- Progress is reported as `0–100` with optional `records_total`, `records_processed`, and `current_item`.

## Task 1: Persisted queue schema

Add an Alembic PostgreSQL migration creating `market_data.sync_jobs`:

- `job_id UUID` primary key
- `entity_type` (`STOCK`, `MUTUAL_FUND`)
- `entity_id UUID`/scheme identifier and human-readable `entity_key`
- `sync_type` (`DAILY_METRICS`, `FUNDAMENTALS`, `SHAREHOLDING`, `TECHNICAL_INDICATORS`)
- `force_sync BOOLEAN`
- `status` (`QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `CANCELLED`)
- `progress_percent NUMERIC(5,2)` with 0–100 check
- `records_total`, `records_processed`, `current_item`
- `queued_at`, `started_at`, `completed_at`, `last_error`, `result JSONB`
- created/updated timestamps

Add indexes for active jobs by entity and queue ordering by `queued_at`. Add the partial uniqueness constraint for active duplicates.

## Task 2: Queue service and worker lifecycle

Replace the in-memory `_jobs` registry in `backend_api/app/sync_queue.py` with a repository-backed queue service:

1. Atomically insert a queued job; on active-key conflict return the existing job with `duplicate=true`.
2. Record `queued_at` at insertion and `started_at` immediately before work begins.
3. Update status/progress in the database throughout execution.
4. Record success/failure, terminal timestamps, result payload, and error text.
5. Reconcile jobs left `RUNNING` after process restart as `FAILED`/`RETRYABLE` on startup.
6. Keep the worker abstraction independent of the specific sync implementation.

## Task 3: Separate sync handlers

Create four handlers with explicit contracts:

- `sync_daily_metrics(entity, force)`
- `sync_fundamentals(entity, force)`
- `sync_shareholding(entity, force)`
- `sync_technical_indicators(entity, force)`

Each handler must support incremental mode (watermark/existing-row checks) and force mode (re-fetch/recalculate all available history), update progress callbacks, and return counts. Fundamentals and shareholding should reuse the Screener parser; technical indicators should reuse the cached calculation service; daily metrics should preserve provider-over-calculated precedence.

## Task 4: API surface

Replace the combined stock sync route with:

- `POST /market-data/stocks/{symbol}/sync/daily-metrics`
- `POST /market-data/stocks/{symbol}/sync/fundamentals`
- `POST /market-data/stocks/{symbol}/sync/shareholding`
- `POST /market-data/stocks/{symbol}/sync/technical-indicators`
- Equivalent mutual-fund routes where applicable (`daily-metrics`/`fundamentals`/`shareholding` only if supported; NAV history for technical is invalid).

Each accepts `force`, returns the persisted job DTO, and returns the existing active job for duplicates. Add:

- `GET /market-data/sync/jobs/{job_id}`
- `GET /market-data/sync/jobs?entity_type=&entity_key=&status=`
- `GET /market-data/stocks/{symbol}/sync/status` and mutual-fund equivalent as convenience views.

Return `409` only for invalid/incompatible sync types; duplicate active requests should be a successful idempotent response with `duplicate=true`.

## Task 5: React UI behavior

1. Add typed API methods for each sync route and job/status/queue endpoints.
2. On detail pages, render separate buttons for daily metrics, fundamentals, shareholding history, and technical indicators.
3. Poll the job endpoint while queued/running; show a compact snackbar with queued, started, progress, success, and failure states.
4. Display queue position, queued time, start time, processed/total counts, and current item where available.
5. Disable only the matching sync button while its job is active. Disable “Force full sync” for that same sync type whenever an active job exists; other stocks and other sync types remain usable.
6. Enable force sync again only after the matching job reaches `SUCCEEDED` or `FAILED` (not merely after the POST returns).
7. Add a collapsible “Sync queue” panel listing active jobs across the portfolio.

## Task 6: Tests and rollout

- Migration tests for enums, progress bounds, timestamps, and active duplicate uniqueness.
- Queue tests for duplicate insertion, FIFO ordering, start/completion timestamps, failure capture, and restart reconciliation.
- Handler tests for incremental versus force behavior and progress callbacks.
- API tests for separate routes, idempotent duplicate responses, status filtering, and invalid sync types.
- React tests for per-job button disabling, polling transitions, snackbar states, and queue rendering.
- Roll out migration first, then backend queue routes, then UI; preserve old combined routes temporarily as compatibility aliases returning the new job DTO.
