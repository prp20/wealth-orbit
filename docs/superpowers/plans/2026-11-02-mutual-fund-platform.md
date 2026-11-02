# Mutual Fund Platform Implementation Plan

## Understanding of the requirement

The mutual-fund experience should become a first-class market-data feature, comparable to stocks:

- A mutual-fund detail route: `/ui/mutualfunds/{scheme_id}`.
- Historical NAV charts and date-range retrieval.
- Native ingestion using the mutual-fund Python ecosystem, with behavior informed by the Nivesh server but implemented in this repository.
- Fund metadata, NAV history, benchmark/index history, calculated performance/risk metrics, comparisons, similar funds, and sync status.
- Queue-backed incremental and force synchronization.
- UI sections that are collapsed by default and independently expandable.

The Nivesh server is a reference implementation only. Its source files and data are not copied into this project.

## Nivesh capabilities mapped during audit

The reference code contains these mutual-fund capabilities:

1. `FundMaster`: scheme metadata, AMC/category/subcategory, plan type, benchmark mapping, ISIN, inception date, manager data, active state.
2. `FundNavHistory`: daily NAV history keyed by scheme and date.
3. `BenchmarkMaster` and `BenchmarkNavHistory`: benchmark metadata and historical index values.
4. `FundMetrics` and `BenchmarkMetrics`: current NAV, CAGR, absolute returns, volatility, Sharpe, Sortino, drawdown, alpha, beta, capture ratios, tracking error, information ratio, and data-completeness metadata.
5. AMFI/mftool sync: historical NAV download, retry behavior, normalization, watermark-aware bulk upsert, and per-fund ETL status.
6. Optional Kuvera/Captnemo enrichment by ISIN: AUM, expense ratio, rating, volatility, manager/fund metadata.
7. Analytics: daily returns, annualized risk, CAGR/absolute returns, capture ratios, alpha/beta, maximum drawdown, and benchmark-relative calculations.
8. APIs: fund list/filter/search, fund detail, NAV history, metrics, manual compute/sync, sync status, similar funds, comparisons, benchmark list/detail/history, and benchmark uploads.
9. Operational behavior: stale metrics trigger background refresh, duplicate running jobs are suppressed, retries are used for provider failures, and ETL runs retain errors/results.

## Target architecture in this repository

- Keep personal portfolio holdings/transactions in local SQLite.
- Keep mutual-fund reference, NAV, benchmark, and calculated market data in Supabase `market_data`.
- Reimplement provider adapters and analytics under `portfolio-service/backend/market_data/`.
- Expose stable FastAPI DTOs under `/api/v1/market-data/mutual-funds` and `/api/v1/market-data/benchmarks`.
- Use the persisted sync-job queue for fund NAV, benchmark, and metric jobs.
- Use UUID/reference IDs already present in this project; do not introduce a second provider registry.

## Implementation tasks

### 1. Schema and lineage audit

- Verify the live columns and keys in `mutual_fund_reference`, `mutual_fund_nav_history`, `index_reference`, `index_daily_history`, `data_sources`, and `sync_jobs`.
- Add migrations for missing fund metadata, benchmark mapping, calculated fund metrics, and metric calculation timestamps.
- Add source IDs, watermarks, completeness fields, and constraints needed for idempotent UPSERTs.
- Document source-to-table lineage and provider precedence.

### 2. Native provider adapters

- Implement an AMFI/mftool adapter with retries, date/NAV normalization, timeout handling, and a clear provider interface.
- Implement benchmark/index history ingestion using the existing index reference data and yfinance/provider mapping where applicable.
- Implement optional ISIN-based enrichment as a separate adapter; enrichment failure must not fail NAV ingestion.
- Add fixture-driven tests with mocked provider responses; no live provider calls in tests.

### 3. NAV and benchmark sync services

- Implement incremental sync using the latest stored date.
- Implement force sync with full historical UPSERT.
- Track records fetched, inserted, updated, skipped, latest date, and errors.
- Update persisted queue progress and timestamps.
- Suppress duplicate active jobs for the same scheme/provider/sync type.

### 4. Analytics service

Reimplement the useful Nivesh analytics as pure functions and a persistence service:

- Daily returns
- 6-month, 1-year, 3-year, 5-year, and 10-year absolute returns
- 3-year and 5-year CAGR
- Annualized volatility
- Sharpe and Sortino
- Maximum drawdown
- Alpha and beta versus benchmark
- Upside/downside capture
- Tracking error and information ratio
- Data completeness and insufficient-history flags

Use explicit annualization/risk-free-rate constants and return NULL where the NAV/benchmark history is insufficient. Never serialize NaN or infinity.

### 5. FastAPI API surface

Add or standardize:

- `GET /api/v1/market-data/mutual-funds`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/history`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/metrics`
- `POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/nav`
- `POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/metrics`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/sync/status`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/similar`
- `GET /api/v1/market-data/mutual-funds/compare?schemes=...`
- Benchmark list/detail/history endpoints.

Each sync endpoint returns a persisted job DTO. Duplicate active requests return the existing job. Metrics GET may trigger a background metrics refresh only when data is absent/stale, while returning the last known metrics and job status.

### 6. React UI

- Add route `/mutualfunds/:schemeId` and make `/mutualfunds` the list route.
- Keep `/ui` landing on portfolio overview.
- Make the mutual-fund detail page visually parallel to stock detail:
  - Summary metadata
  - NAV history chart
  - Performance metrics
  - Risk metrics
  - Benchmark comparison
  - Similar funds
  - Sync controls and persisted job status
- Collapse all sections by default with accessible independent expand/collapse controls.
- Poll sync jobs until terminal status; disable only the matching force-sync button while active.
- Show queue position, start time, progress, records, success, and errors in a snackbar and sync panel.

### 7. Verification

- Unit-test provider normalization and analytics against known NAV series.
- Test incremental/force UPSERT semantics and duplicate suppression.
- Test stale metric refresh and insufficient-history behavior.
- Test every API route and direct browser refresh at `/ui/mutualfunds/{scheme_id}`.
- Add a runbook showing how to sync one scheme, sync all schemes, recompute metrics, inspect jobs, and verify latest NAV dates.

## Clarifications needed before implementation

1. Should “all mutual-fund features” include the Nivesh scorer modules (`fund_scorer` and `fundamental_scorer`), or should V1 stop at metadata, NAV, benchmarks, analytics, comparison, and similar funds?
2. Should optional AUM/expense-ratio/rating enrichment use the Captnemo/Kuvera endpoint, or should we restrict V1 to AMFI/mftool plus existing Supabase data?
3. Should benchmark/index history be synced automatically with each fund sync, or remain a separate benchmark job that fund metrics consume?

## Agent execution instructions

The implementing agent must follow these instructions literally:

### Boundaries

- Work only in this repository.
- Read the Nivesh server for behavior and field mappings only. Do not import its modules, copy its files, copy its database, or copy its data.
- Preserve the existing split: portfolio transactions/holdings remain local SQLite; market reference/history/analytics remain Supabase PostgreSQL.
- Preserve existing public API routes through compatibility aliases.
- Never report a sync as successful unless provider fetch and persistence both completed.

### Mandatory pre-audit

Before editing, inspect live columns for mutual-fund/index tables, existing reference-service queries, migration head, UUID support, React routes/API client/charts, and these Nivesh reference modules: app/models.py, app/crud.py, app/sync.py, app/analytics.py, app/routers/funds.py, app/routers/navs.py, app/routers/metrics.py, pipeline/price_ingestion.py, and pipeline/metric_recompute.py. Record schema mismatches as migration decisions.

### Provider adapter

Create portfolio-service/backend/market_data/providers/mutual_funds.py with fetch_historical_nav(scheme_code, start_date=None). Use mftool.Mftool().get_scheme_historical_nav(scheme_code, True) behind a thread boundary, normalize DataFrame/list responses to nav_date/date plus Decimal nav_value, retry transient failures three times, reject malformed dates/NAVs, and keep optional enrichment failures non-fatal.

### Sync services

Create portfolio-service/backend/market_data/mutual_fund_sync.py with sync_nav, sync_benchmark, and recompute_metrics. Incremental mode uses the latest stored NAV date as watermark; force mode fetches complete history and UPSERTs every observation. Return fetched/inserted/updated/skipped counts, latest date, and warnings. Metrics must record insufficient-history/completeness flags and never persist NaN or Infinity.

### Queue

Use market_data.sync_jobs with job types MF_NAV, MF_BENCHMARK, and MF_METRICS. Enforce active uniqueness by entity, type, and force flag. Persist queued/started/progress/completed/error/result fields. Workers must call real sync services, duplicate requests return the existing job ID, and terminal jobs remain queryable.

### API contract

Implement and test:

- GET /api/v1/market-data/mutual-funds/{scheme_id}/history?from_date=&to_date=&limit=
- GET /api/v1/market-data/mutual-funds/{scheme_id}/metrics
- POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/nav?force=
- POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/metrics?force=
- GET /api/v1/market-data/mutual-funds/{scheme_id}/sync/status
- GET /api/v1/market-data/mutual-funds/{scheme_id}/similar
- GET /api/v1/market-data/mutual-funds/compare?schemes=A,B

Use stable DTOs, return 404 for unknown schemes, and return an empty list with metadata when history is empty.

### React contract

Implement /ui/mutualfunds/:schemeId with summary, NAV chart, performance, risk, benchmark comparison, similar funds, and sync-status sections. Use an accessible CollapsibleSection component; every section is closed by default. Put sync buttons in section headers, poll jobs every second, disable only the matching active button, show queue position/timestamps/progress/errors, and refetch after success. Preserve portfolio overview as the /ui landing page.

### Completion gate

Do not claim completion until a fixture scheme supports incremental and force sync, history returns the latest persisted date, metrics return persisted metrics or explicit insufficient-data status, duplicate jobs reuse the existing ID, direct nested UI navigation returns the React app, tests pass, and the React production build succeeds.
