# Daily Metrics and Technical Indicators Recovery Plan

## Findings

1. The sync route currently treats `daily_metrics` and `technical` as successful no-op jobs. Only `fundamentals` calls a real ingestion function. This creates false `SUCCEEDED` jobs with zero database writes.
2. `provider_metrics_from_ratios()` exists but is never called by a sync handler, and no repository function writes `market_data.stock_daily_metrics`.
3. The technical calculation module is pure/tested code, but there is no service that reads `stock_daily_prices`, invokes it, and UPSERTs into `stock_technical_indicators`.
4. The technical GET route only reads cached rows. It does not calculate missing/stale indicators on demand, so an empty table always stays empty.
5. The technical cache schema uses a JSONB value in the primary key. The service must use one canonical JSON representation and stable indicator periods or repeated requests can miss existing rows.
6. The queue status route for a stock currently returns `idle` unconditionally; the UI cannot reliably lock a panel or poll its job.
7. Progress is only set to 10/100. The worker has no progress callback and cannot report records processed/current item.
8. Daily metrics need a clear date policy: provider metrics are snapshot data and should be written for the sync date, while fallback calculations must never overwrite provider values.

## Implementation plan

### 1. Add repositories and explicit sync contracts

Create a market-data repository layer with functions for stock UUID resolution, latest price/financial values, daily metric UPSERTs, technical cache reads, technical UPSERTs, and stale invalidation. Define typed sync results containing `records_total`, `records_processed`, `current_item`, and warnings.

### 2. Implement daily-metrics ingestion

Add `sync_daily_metrics(symbol, force, progress)`:

- Fetch the Screener page once and parse its ratio panel.
- Map Market Cap, Stock P/E, Price to Book, Dividend Yield, Book Value, ROCE, and ROE.
- Normalize Indian units and percentages.
- Use the latest available trading date or explicit sync date as `metric_date`.
- Write provider values with `calculation_method=PROVIDER` and the Screener source ID.
- Calculate PE/PB/dividend yield only when provider values are missing and reliable inputs exist.
- Use conflict logic that preserves provider values from calculated fallbacks.
- Return inserted/updated counts and warnings.

Add a dedicated route:

```text
POST /market-data/stocks/{symbol}/sync/daily-metrics
```

The existing generic route should delegate to this handler for compatibility, never return a fake success.

### 3. Implement technical calculation-and-persistence service

Create `technical_service.py`:

- Load chronological OHLCV closes from `stock_daily_prices`.
- Validate requested indicator/configuration.
- Fetch warm-up history before the requested date range.
- Call the pure RSI/SMA/EMA/MACD/Bollinger functions.
- Persist output rows with canonical parameters and component names.
- Mark rows `CURRENT` with `calculated_at` after successful writes.
- Read and reuse `CURRENT` cache rows.
- Recalculate missing/STALE rows only when requested.
- Mark affected rows stale when price ingestion changes a historical date.

Add:

```text
POST /market-data/stocks/{symbol}/sync/technical-indicators
GET  /market-data/stocks/{symbol}/technical-indicators
```

The GET endpoint must support indicator, period/configuration, and date-range parameters and invoke on-demand calculation when cache rows are missing or stale.

### 4. Make queue execution truthful and observable

- Replace placeholder lambdas with the real daily-metrics and technical handlers.
- Add a progress callback to update `sync_jobs.progress_percent`, `records_processed`, `records_total`, and `current_item`.
- Implement `GET /market-data/sync/jobs/{job_id}` and entity/type status queries using persisted data.
- Return the existing active job for duplicates, keyed by entity, sync type, and force mode.
- On worker exceptions, persist the full error and return `FAILED`, never `SUCCEEDED`.
- Add startup recovery for jobs left `RUNNING` after a process restart.

### 5. Fix React data flow and per-panel locking

Create a reusable `PanelSyncControls` component receiving `entityKey`, `syncType`, and query invalidation keys.

- Render one control group in each daily-metrics and technical-indicators panel.
- POST the dedicated route and retain the returned `job_id`.
- Poll the job endpoint every second while `QUEUED`/`RUNNING`.
- Disable both normal and force buttons for that panel while active.
- Re-enable after `SUCCEEDED` or `FAILED` only.
- Show a snackbar with queued time, start time, progress, queue position, success count, and error details.
- Invalidate/refetch the relevant panel query after success.

### 6. Validate database and API state for 3MINDIA

Add a diagnostic endpoint/CLI query returning:

- latest `stock_daily_prices` date
- daily metric dates and values
- technical indicator count/latest date/status
- active and terminal sync jobs
- latest job error/result

Use it to distinguish missing source data from failed ingestion and to verify that a successful job actually changed row counts.

### 7. Tests and rollout

- Unit tests for provider metric mapping, unit conversion, provider precedence, and NULL fallbacks.
- Technical tests for every supported indicator plus persistence/cache reuse/stale recalculation.
- Queue tests proving no false success, duplicate suppression, progress updates, and failure persistence.
- API tests for dedicated routes and 3MINDIA diagnostics.
- React tests for per-panel polling and button locking.
- Apply migrations, run backend tests, build React, then perform one-stock sync verification before enabling batch usage.

### 8. Fix React SPA refresh routing and default landing page

The `/ui` application is a client-side React SPA, but a browser refresh on a nested route such as `/ui/stocks/3MINDIA` currently asks FastAPI/StaticFiles for a physical file named `stocks/3MINDIA`, producing a 404 JSON response instead of returning `index.html`.

Implement the routing fix as follows:

1. Keep API routes ahead of the UI fallback so `/api/v1/*` continues returning JSON and is never rewritten to the SPA.
2. Add an explicit UI catch-all route/middleware for non-API paths under `/ui` that returns `frontend-react/dist/index.html` when the requested path is not a real asset.
3. Preserve static asset serving for `/ui/assets/*`, including correct content types and cache headers.
4. Ensure both `/ui` and `/ui/` resolve to the SPA entrypoint.
5. Configure React Router with the `/ui` basename, or use a consistent root deployment strategy, so links and refreshes resolve correctly when served by FastAPI.
6. Make the default route `/` render the portfolio overview. The landing behavior must remain the portfolio overview even when no portfolio has loaded yet; show a loading/empty state rather than redirecting to stocks or another reference page.
7. Verify direct navigation and browser refresh for:
   - `/ui`
   - `/ui/`
   - `/ui/stocks`
   - `/ui/stocks/3MINDIA`
   - `/ui/mutual-funds`
   - `/ui/transactions`
   - `/api/v1/health`
8. Add FastAPI route tests asserting nested UI paths return HTML with status 200 while API paths retain their JSON behavior. Add a production-build smoke test that opens a nested route directly rather than navigating from `/ui`.

### 9. Document and preserve mutual-fund data lineage

The implementation plan must include a data-lineage section for the mutual-fund datasets populated from:

`/home/prasad/dev_home/projects/stock_platform/nivesh-server`

Before changing mutual-fund behavior, inventory and document the source pipeline modules and destination tables:

- Mutual-fund master/reference data: scheme code, scheme name, AMC, category, subcategory, plan type, option type, active status.
- AMC reference data and AMC-to-scheme relationships.
- Category and subcategory reference data.
- Daily NAV history and its source/provider identifiers.
- Benchmark/index mappings and index/NAV history where available.
- Any calculated fund metrics, return series, risk metrics, benchmark-relative metrics, or classification fields populated by the Nivesh pipelines.
- Ingestion run/error tracking, source priority, watermark/deduplication, and UPSERT behavior.

Trace each dataset from its Nivesh-server pipeline/scraper through the loader or migration into the Supabase `market_data` tables, including source, field mapping, date/NAV normalization, identifier mapping, duplicate handling, incremental/force semantics, missing/revised values, and the API/UI consumer.

Add a mutual-fund data-lineage/runbook document and a verification command reporting row counts and latest dates for every mutual-fund table. Reuse the existing source and ingestion conventions rather than adding a second provider registry.

### 10. Collapsible detail sections

All stock and mutual-fund detail sections must be collapsed by default and independently expandable:

- Price history
- Daily metrics
- Fundamentals
- Shareholding history
- Technical indicators
- Mutual-fund NAV, returns, benchmark, and metric sections

Implement a reusable React `CollapsibleSection` component with:

- Closed initial state.
- Accessible button semantics (`aria-expanded`, `aria-controls`).
- Independent state per section.
- Optional persisted open/closed preference scoped to the current entity and section.
- Lazy loading of expensive tables/charts on first expansion.
- Loading, empty, and error states inside the expanded body.

Sync controls remain visible in the collapsed header, while data bodies/charts remain hidden until expansion. Force-sync buttons remain disabled while the matching persisted job is queued or running, regardless of section state.
