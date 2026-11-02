# Mutual Fund Performance and Enrichment Execution Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Every task is independently testable; do not skip the failing-test step.

**Goal:** Build a persisted, benchmark-aware mutual-fund analytics pipeline and UI for returns, risk, fund facts, and Groww-backed index history.

**Architecture:** Supabase PostgreSQL owns market reference data, NAVs, benchmarks, enrichment, and metric snapshots. Local SQLite remains portfolio-only. Providers fetch external data; pure functions calculate analytics; queue workers persist results; FastAPI exposes DTOs; React only reads persisted DTOs and triggers jobs.

**Tech Stack:** Python 3.13, psycopg2, FastAPI, Alembic, pandas, mftool/AMFI, Groww API + `pyotp`, React/Vite, TanStack Query.

**Spec:** `docs/superpowers/plans/2026-11-02-mutual-fund-performance-and-enrichment.md`

## Non-negotiable behavior

- Never report a sync as successful unless fetch, normalization, and DB commit all succeed.
- Never write NaN, infinity, negative NAV, or fabricated enrichment values.
- Incremental sync uses the latest persisted date; force sync re-fetches full history and UPSERTs idempotently.
- Metrics use only persisted NAV/benchmark data; GET requests never fetch providers.
- Missing history, benchmark, or enrichment is represented by `available=false`, `reason`, and nullable values.
- All detail sections are collapsed by default; daily NAV rows are nested behind “View daily NAV data”.
- TOTP seed, generated code, access token, API key, and raw auth payload never enter DB, logs, queue results, or API responses.

## Data contracts

### `mutual_fund_metric_snapshots`

Use one row per `(scheme_id, as_of_date, metric_period, calculation_version)`. Required columns:

`metric_snapshot_id UUID`, `scheme_id UUID`, `as_of_date DATE`, `metric_period VARCHAR(10)` (`1Y`,`3Y`,`5Y`,`10Y`,`ALL`), `current_nav NUMERIC`, `trailing_return NUMERIC`, `cagr NUMERIC`, `rolling_latest NUMERIC`, `rolling_min NUMERIC`, `rolling_max NUMERIC`, `rolling_median NUMERIC`, `standard_deviation NUMERIC`, `sharpe NUMERIC`, `sortino NUMERIC`, `maximum_drawdown NUMERIC`, `alpha NUMERIC`, `beta NUMERIC`, `tracking_error NUMERIC`, `information_ratio NUMERIC`, `benchmark_index_id UUID`, `benchmark_as_of_date DATE`, `observations INTEGER`, `aligned_observations INTEGER`, `risk_free_rate NUMERIC`, `annualization_factor INTEGER`, `available BOOLEAN`, `reason TEXT`, `calculation_version VARCHAR(30)`, timestamps.

### `mutual_fund_enrichment`

Use one row per `(scheme_id, as_of_date, source_id)`: `enrichment_id UUID`, `scheme_id UUID`, `as_of_date DATE`, `aum NUMERIC`, `expense_ratio NUMERIC`, `exit_load TEXT`, `yield_to_maturity NUMERIC`, `yield_to_maturity_unit VARCHAR(20)`, `fund_manager TEXT`, `rating TEXT`, `source_id UUID`, `provider_status VARCHAR(20)`, `raw_payload_hash VARCHAR(64)`, `warnings JSONB`, timestamps.

### `index_daily_history` and provider mapping

`index_daily_history(index_id, history_date, open, high, low, close, volume, source_id, created_at, updated_at)` with primary key `(index_id, history_date)`. Add mapping fields/table for `index_id`, provider (`GROWW`), exchange, segment, trading symbol, TRI flag, active flag, last successful date.

## Task 1 — Baseline audit and fixtures

**Files:**
- Create: `tests/market_data/fixtures/mutual_fund_nav.json`
- Create: `tests/market_data/fixtures/benchmark_candles.json`
- Create: `tests/market_data/test_mutual_fund_data_contract.py`
- Modify: `docs/mutual-fund-data-lineage.md`

- [ ] Inspect live PostgreSQL columns for `mutual_fund_reference`, `mutual_fund_nav_history`, `index_reference`, `index_daily_history`, `data_sources`, and `sync_jobs`.
- [ ] Record every mismatch between live schema and this plan before writing migration code.
- [ ] Add deterministic fixture NAV series covering fewer than 1Y, exactly 1Y, and 10Y windows; include weekend gaps and malformed provider values.
- [ ] Add benchmark fixture with aligned, missing, duplicate, and zero-variance cases.
- [ ] Run `pytest tests/market_data/test_mutual_fund_data_contract.py -v`; expected initial failure for missing contract helpers is acceptable.

## Task 2 — Database migration

**Files:**
- Create: `migrations/alembic/versions/006_mutual_fund_analytics.py`
- Create: `migrations/alembic/versions/007_groww_index_provider.py`
- Modify: `portfolio-service/backend/reference_models.py`
- Test: `tests/market_data/test_mutual_fund_schema_contract.py`

- [ ] Create the three tables/contracts above with UUID keys, foreign keys, uniqueness, indexes, timestamps, and check constraints.
- [ ] Use nullable metric/enrichment values and explicit `available/reason` fields; do not use zero as “missing”.
- [ ] Add constraints for `expense_ratio`, `yield_to_maturity`, percentage metrics, and positive index close values.
- [ ] Make migrations PostgreSQL-only where existing project conventions require it; keep downgrade paths safe.
- [ ] Add schema introspection tests for columns, primary keys, uniqueness, and nullable fields.
- [ ] Run `uv run alembic upgrade head` against a test database and rerun schema tests.

## Task 3 — mftool NAV provider

**Files:**
- Create: `portfolio-service/backend/market_data/providers/mutual_funds.py`
- Modify: `portfolio-service/backend/mutual_fund_service.py`
- Test: `tests/market_data/test_mutual_fund_provider.py`

- [ ] Define `fetch_historical_nav(scheme_code: str, start_date: date | None = None) -> ProviderResult`.
- [ ] Call `Mftool().get_scheme_historical_nav(scheme_code, as_json=True)`; extract `payload["data"]`.
- [ ] Normalize JSON/list/DataFrame shapes, ISO and `DD-Mon-YYYY` dates, decimal NAV strings, and reject `NAV <= 0`.
- [ ] Retry transient network/provider failures three times with bounded backoff; include provider and error code in diagnostics.
- [ ] Preserve current source-ID/advisory-lock behavior and return fetched/inserted/updated/skipped counts.
- [ ] Test malformed rows, zero NAV, empty payload, retry success, force mode, incremental watermark, and idempotent rerun.

## Task 4 — Groww TOTP and index provider

**Files:**
- Create: `portfolio-service/backend/market_data/providers/groww_auth.py`
- Create: `portfolio-service/backend/market_data/providers/groww_indices.py`
- Create: `portfolio-service/backend/market_data/groww_sync.py`
- Test: `tests/market_data/test_groww_auth.py`
- Test: `tests/market_data/test_groww_indices.py`

- [ ] Read `GROWW_API_KEY`, `GROWW_TOTP_SECRET`, timeout, and retry settings from environment only.
- [ ] Implement `GrowwAuthProvider.get_access_token() -> AccessToken` using `pyotp.TOTP(secret).now()` and `POST /v1/token/api/access` with `key_type=totp`.
- [ ] Cache token in memory until expiry; protect refresh with a lock; refresh once on 401; retry 429/5xx with bounded backoff.
- [ ] Redact secrets in request logging and central JSON logs.
- [ ] Implement `fetch_index_candles(provider_symbol, start, end, interval_minutes=1440)` with Groww `exchange=NSE`, `segment=CASH`, and candle normalization.
- [ ] Resolve and validate actual Groww symbols before enabling mappings; do not assume labels such as `NIFTY_500_TRI` are exchange symbols.
- [ ] Persist these requested benchmark labels and category defaults: NIFTY 100 TRI, NIFTY Midcap 150 TRI, NIFTY Smallcap 250 TRI, NIFTY 500 TRI, NIFTY 500 Multicap 50:25:25 TRI, NIFTY LargeMidcap 250 TRI.
- [ ] Test token exchange, cache, expiry, 401, 429, malformed candles, missing symbols, watermark sync, force sync, and all eight mapping keys.

## Task 5 — Enrichment provider

**Files:**
- Create: `portfolio-service/backend/market_data/providers/enrichment.py`
- Test: `tests/market_data/test_mutual_fund_enrichment.py`

- [ ] Define `fetch_fund_facts(scheme_code, isin=None) -> EnrichmentResult` with provider-specific adapters.
- [ ] Normalize AUM, expense ratio, exit load, YTM, manager, and rating without coercing unknown values to zero.
- [ ] Treat enrichment failures as non-fatal to NAV sync; persist provider status/warnings when possible.
- [ ] Test partial payloads, percentage formats, crore/lakh AUM values, exit-load text, debt YTM, malformed fields, and provider timeout.

## Task 6 — Pure analytics engine

**Files:**
- Create: `portfolio-service/backend/market_data/mutual_fund_analytics.py`
- Test: `tests/market_data/test_mutual_fund_analytics.py`

- [ ] Implement exact typed functions: `daily_returns(nav: DataFrame)`, `trailing_return(nav, years)`, `cagr(nav, years)`, `rolling_returns(nav, years)`, `annualized_stddev(returns)`, `sharpe_ratio(returns, risk_free_rate)`, `sortino_ratio(returns, risk_free_rate)`, `max_drawdown(nav)`, `align_benchmark(fund, benchmark)`, `alpha_beta(fund_returns, benchmark_returns, risk_free_rate)`, and `tracking_error_information_ratio(...)`.
- [ ] Use nearest prior NAV for lookbacks; never use future observations.
- [ ] Use 252 annualization for daily returns and a configured risk-free rate; persist both assumptions.
- [ ] Return typed `None`/availability reasons for insufficient history, zero benchmark variance, zero downside deviation, and absent benchmark.
- [ ] Test exact synthetic expected values and all five Review Focus cases.

## Task 7 — Persistence and queue orchestration

**Files:**
- Create: `portfolio-service/backend/market_data/mutual_fund_sync.py`
- Modify: `backend_api/app/sync_queue.py`
- Test: `tests/market_data/test_mutual_fund_sync.py`

- [ ] Implement `sync_nav`, `sync_benchmark`, `sync_enrichment`, and `recompute_metrics`.
- [ ] Enforce dependency order: NAV → benchmark (if mapped) → enrichment → metrics; metrics may persist fund-only results when benchmark is unavailable.
- [ ] Add queue types `MF_NAV`, `MF_BENCHMARK`, `MF_ENRICHMENT`, `MF_METRICS`, and `INDEX_HISTORY` with active duplicate suppression.
- [ ] Persist job progress, start/completion timestamps, fetched/processed counts, warnings, and terminal errors.
- [ ] Test force/incremental reruns, duplicate job IDs, prerequisite failures, partial enrichment, and rollback on DB errors.

## Task 8 — FastAPI contracts

**Files:**
- Modify: `backend_api/app/market_data_routes.py`
- Modify: `portfolio-service/backend/reference_service.py`
- Modify: `backend_api/app/portfolio_backend.py`
- Test: `tests/market_data/test_mutual_fund_api_contract.py`

- [ ] Keep existing detail/history routes compatible.
- [ ] Add `GET /mutual-funds/{scheme}/metrics` returning persisted snapshots and availability metadata.
- [ ] Add `GET /mutual-funds/{scheme}/benchmark` and `/benchmark/history`.
- [ ] Add `GET /mutual-funds/{scheme}/enrichment`.
- [ ] Add `GET /mutual-funds/{scheme}/history?from_date=&to_date=&limit=` with bounded pagination metadata.
- [ ] Add `POST /mutual-funds/{scheme}/sync/benchmark`, `/sync/enrichment`, and `/sync/metrics`; return persisted job DTOs.
- [ ] Add index list/detail/history endpoints and a benchmark comparison endpoint.
- [ ] Validate unknown scheme/index as 404, missing prerequisites as 409, invalid periods as 422, and provider failures as terminal job errors.
- [ ] Test response fields, empty states, duplicate jobs, and read-only GET behavior.

## Task 9 — React detail-page implementation

**Files:**
- Modify: `frontend-react/src/api.ts`
- Modify: `frontend-react/src/app/App.tsx`
- Create: `frontend-react/src/components/BenchmarkComparison.tsx`
- Modify: `frontend-react/src/components/MarketChart.tsx`
- Modify: `frontend-react/src/extra.css`
- Test: frontend build and route smoke test

- [ ] Keep `/ui/mutualfunds/:schemeId` as the route and preserve direct refresh behavior.
- [ ] Keep NAV chart visible in collapsed NAV History; put daily rows inside a nested disclosure.
- [ ] Add collapsed sections: Performance, Rolling returns, Risk ratios, Benchmark comparison, Fund facts, Similar funds.
- [ ] Render trailing/rolling 1Y/3Y/5Y/10Y, alpha, beta, Sharpe, Sortino, standard deviation, YTM, expense ratio, exit load, AUM, benchmark, source, and as-of dates.
- [ ] Display `Not available` with `reason` rather than blank or zero values.
- [ ] Add matching sync controls, queue status, and refetch after terminal success.
- [ ] Run `npm run build` and verify `/ui`, `/ui/mutualfunds`, and `/ui/mutualfunds/{scheme}`.

## Task 10 — End-to-end verification and handoff

**Files:**
- Create: `docs/runbooks/mutual-fund-analytics.md`
- Modify: `docs/mutual-fund-data-lineage.md`

- [ ] Configure a non-production Groww credential set through environment variables only.
- [ ] Run one scheme through NAV, benchmark, enrichment, and metric jobs; inspect persisted rows and job results.
- [ ] Run each sync twice; verify incremental second runs are up-to-date and idempotent.
- [ ] Verify a fund without benchmark still has fund-only metrics and explicit benchmark-unavailable state.
- [ ] Verify a debt fund with enrichment YTM and a growth fund without YTM both render correctly.
- [ ] Run `pytest`, `npm run build`, `git diff --check`, and an import smoke test before commit.
- [ ] Document token setup, required Groww subscription/approval, secret handling, benchmark symbol validation, formulas, and troubleshooting.

## Suggested implementation order

1. Tasks 1–2: audit and schema.
2. Tasks 3–5: provider adapters.
3. Task 6: pure analytics with tests.
4. Task 7: persistence/queue orchestration.
5. Task 8: API contracts.
6. Task 9: UI.
7. Task 10: end-to-end verification and commit.

## Completion gate

Do not claim completion until a fixture scheme demonstrates force and incremental NAV sync, Groww-authenticated benchmark sync is mocked and tested, enrichment fields persist when supplied, all requested metrics return persisted values or explicit unavailable reasons, duplicate jobs reuse IDs, direct UI refresh works, all sections are collapsed by default, tests pass, and the React production build succeeds.
