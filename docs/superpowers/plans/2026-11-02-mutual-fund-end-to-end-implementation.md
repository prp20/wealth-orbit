# Mutual Fund End-to-End Implementation Plan

## Objective

Build mutual funds as a complete vertical slice in Wealth Orbit, using the Nivesh server only as a behavioral reference. The implementation must cover database schema, provider adapters, ingestion pipelines, persistent jobs, analytics, FastAPI contracts, React routing/components, deployment serving, tests, and documentation.

## Current-state diagnosis

- The current project has mutual-fund reference and NAV read queries, but no complete native sync/analytics pipeline.
- `mutual_fund_service.py` is currently a thin NAV prototype and does not provide the full Nivesh feature set.
- The queue has persisted jobs but routes still include placeholder work and status endpoints that return `idle` unconditionally.
- React currently uses a shared, minified detail component and lacks a dedicated `/ui/mutualfunds/:schemeId` route architecture.
- FastAPI UI serving needs explicit SPA fallback for direct nested-route refreshes.
- The current database has reference/NAV tables but must be audited before adding metrics, benchmark, enrichment, and job fields.

## Reference behavior to reproduce, not copy

Study these Nivesh modules and implement equivalent behavior locally:

- `app/models.py`: fund master, NAV, benchmark, fund metrics, benchmark metrics.
- `app/sync.py`: mftool historical NAV fetch, retry, normalization, optional ISIN enrichment, benchmark lookup, analytics orchestration.
- `app/analytics.py`: daily returns, CAGR, absolute returns, volatility, Sharpe, Sortino, drawdown, alpha/beta, capture ratios, tracking error, information ratio, completeness.
- `app/crud.py`: filtering, pagination, bulk NAV UPSERT, metric UPSERT, similar-fund and comparison queries.
- `app/routers/funds.py`: list/detail/search/filter/similar/compare contracts.
- `app/routers/navs.py`: history, date watermark, bulk ingestion.
- `app/routers/metrics.py`: stale detection, background refresh, status, manual compute, duplicate suppression.
- `pipeline/price_ingestion.py`: benchmark NAV ingestion and AMFI orchestration.
- `pipeline/metric_recompute.py`: benchmark-aware metric recomputation.

Do not import Nivesh modules, copy its files, copy its database, or copy personal data.

## Implementation workstreams

### A. Database and migrations

Audit live Supabase columns first. Add one migration for any missing canonical fields:

- Fund metadata enrichment: ISIN, inception date, benchmark reference, manager, active state.
- Fund NAV history: provider/source ID, updated timestamp, uniqueness on scheme/date.
- Benchmark reference/history.
- Fund metrics: latest NAV/date, AUM, TER, rating, return/risk/relative metrics, completeness, calculation timestamps.
- Sync-job entity/type/status fields and active duplicate uniqueness.

Use foreign keys to existing scheme/index/source IDs. Add only query-supported indexes. Make migrations PostgreSQL-safe and SQLite-safe. Add downgrade paths.

### B. Provider and normalization layer

Create native modules under `portfolio-service/backend/market_data/providers/`:

- `mutual_funds.py`: mftool adapter with retries, timeouts, DataFrame/list normalization, Decimal NAV conversion, invalid-row rejection, and provider error taxonomy.
- `benchmark.py`: benchmark history adapter using the existing index symbol/source mapping.
- `enrichment.py`: optional ISIN/Captnemo-style metadata adapter, isolated so enrichment failures never fail NAV sync.

Expose typed provider contracts and mock them in tests. Do not let provider-specific response fields leak into API DTOs.

### C. Sync pipelines and persistent queue

Create `portfolio-service/backend/market_data/mutual_fund_sync.py` with real handlers:

- `sync_nav(scheme_id, force, progress)`
- `sync_benchmark(index_id, force, progress)`
- `recompute_metrics(scheme_id, force, progress)`
- `sync_full_fund(scheme_id, force, progress)` orchestrating NAV → enrichment → benchmark read → metrics.

Incremental mode uses a date watermark; force mode fetches all provider history and UPSERTs. Every handler returns fetched/inserted/updated/skipped counts, latest date, warnings, and completeness.

Queue requirements:

- Job types: `MF_NAV`, `MF_BENCHMARK`, `MF_METRICS`, `MF_FULL`.
- Persist queued/started/completed timestamps, progress, queue position, current item, result, and error.
- Active duplicate key: entity + job type + force.
- Worker calls real handlers; no placeholder success lambdas.
- Terminal jobs remain queryable; active queue endpoint shows only queued/running.
- Startup recovery marks orphaned jobs failed/retryable.

### D. Analytics and persistence

Implement pure, tested analytics functions and a persistence service:

- Daily NAV returns.
- 6-month, 1-year, 3-year, 5-year, 10-year absolute returns.
- 3-year and 5-year CAGR.
- Annualized volatility.
- Sharpe and Sortino with explicit risk-free-rate/trading-day constants.
- Maximum drawdown.
- Alpha, beta, upside/downside capture, tracking error, information ratio when benchmark data exists.
- Data completeness and insufficient-history flags.

Convert NaN/infinity to NULL. Never fabricate insufficient metrics. Persist calculation period and timestamp.

### E. FastAPI API layer

Implement stable DTOs and these routes:

- `GET /api/v1/market-data/mutual-funds`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/history`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/metrics`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/similar`
- `GET /api/v1/market-data/mutual-funds/compare`
- `POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/nav`
- `POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/metrics`
- `POST /api/v1/market-data/mutual-funds/{scheme_id}/sync/full`
- `GET /api/v1/market-data/mutual-funds/{scheme_id}/sync/status`
- Equivalent benchmark list/detail/history routes.

GET metrics returns last known metrics plus refresh job state when stale. POST sync returns a persisted job DTO and is idempotent for active duplicates. Keep legacy routes as aliases.

### F. React/Vite UI

Refactor `frontend-react/src/app/App.tsx` into maintainable components rather than extending the minified monolith:

- `routes/AppRoutes.tsx`
- `pages/PortfolioOverviewPage.tsx`
- `pages/MutualFundListPage.tsx`
- `pages/MutualFundDetailPage.tsx`
- `components/CollapsibleSection.tsx`
- `components/SyncControls.tsx`
- `components/MutualFundMetrics.tsx`
- `components/NavHistoryChart.tsx`
- `components/FundComparison.tsx`
- `components/SimilarFunds.tsx`

Routes:

- `/ui` → portfolio overview by default.
- `/ui/mutualfunds` → paginated/filterable list.
- `/ui/mutualfunds/:schemeId` → detail page.
- Preserve `/ui/mutual-funds` as a compatibility alias.

Detail parity with stocks:

- Summary metadata.
- NAV line chart with date range.
- Performance metrics.
- Risk metrics.
- Benchmark comparison.
- Similar funds.
- Sync controls with job polling.

All sections are collapsed by default, independently expandable, accessible, and lazy-load expensive data on first expansion. Force sync is disabled only for the matching active job and re-enabled after terminal success/failure. Show snackbar and queue drawer with timestamps, progress, queue position, counts, and errors.

### G. FastAPI SPA serving

- Keep `/api/v1/*` ahead of UI fallback.
- Serve real `/ui/assets/*` files.
- Return `frontend-react/dist/index.html` for `/ui`, `/ui/`, and unknown non-asset nested routes.
- Configure React Router basename consistently.
- Add direct-refresh smoke tests for `/ui/mutualfunds/{scheme_id}`.

### H. Tests, verification, and documentation

- Migration constraints/foreign-key/UPSERT tests.
- Provider fixtures and retry/error tests.
- Incremental/force sync tests.
- Analytics formula and insufficient-history tests.
- Queue lifecycle, duplicate, progress, and restart tests.
- API contract tests for all fund/benchmark/sync routes.
- React tests for routing, collapsed sections, polling, locking, refetch, and empty/error states.
- Production build and direct nested-route browser smoke tests.
- Add a mutual-fund runbook documenting source lineage, sync commands, job inspection, latest-date verification, and provider limitations.

## Acceptance criteria

The work is complete only when:

1. A fixture scheme can run incremental and force NAV sync with persisted counts.
2. NAV history returns the latest persisted date through FastAPI and the UI chart.
3. Metrics are persisted and expose explicit insufficient-data states.
4. Benchmark-relative metrics work when a benchmark is mapped.
5. Duplicate active jobs reuse the same job ID.
6. Direct refresh of `/ui/mutualfunds/{scheme_id}` returns the React app.
7. All detail sections are collapsed initially and independently expandable.
8. React and backend test suites plus production build pass.
