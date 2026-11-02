# Stock Fundamentals and Technical Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (or an equivalent implementation workflow) when executing this plan.

**Goal:** Add provider-backed stock fundamentals, daily valuation metrics, quarterly shareholding history, and on-demand cached technical indicators to the existing Wealth Orbit market-data service without duplicating the current market-data schema or ingestion framework.

**Architecture:** Keep canonical reference and historical data in Supabase PostgreSQL under `market_data`. Add SQL migrations and a repository/service layer in the existing FastAPI backend. Adapt the referenced Screener pipeline into this repository's schema through a provider adapter, retaining `data_sources`, `ingestion_runs`, `ingestion_errors`, UPSERTs, throttling, and checksum/idempotency conventions. Keep indicator math in pure testable functions, with request-time cache orchestration in a service rather than route handlers. Extend existing stock detail APIs and React detail screens.

**Tech Stack:** PostgreSQL/Supabase, Alembic SQL migrations, psycopg2/SQLAlchemy conventions already present in the repository, FastAPI, NumPy/Pandas-compatible numerical code, React + Vite, pytest.

## Scope and non-negotiable constraints

- Inspect and extend the existing `market_data` schema; do not recreate `stock_reference`, `stock_daily_prices`, `data_sources`, or ingestion tables.
- Use existing stock UUIDs and source IDs as foreign keys.
- Preserve provider values: calculated fallbacks may fill NULLs, but must never overwrite provider-supplied daily metrics.
- Keep provider-specific Screener field names and parsing in the adapter/service layer, not in canonical tables.
- Technical calculations use regular daily closes from `stock_daily_prices`; no adjusted OHLC or separate price feed is introduced.
- Technical indicators are on demand and cached; no “calculate every stock” scheduler is added.
- Do not fabricate values when inputs or warm-up history are insufficient.

## Review focus

- Schema keys, enums/check constraints, JSONB parameter normalization, and indexes match the requested uniqueness and query patterns.
- Screener mapping is explicit, unit-safe, checksum/idempotent, rate-limited, and records partial failures through the existing ETL framework.
- Provider-vs-calculated precedence is enforced in SQL/service code.
- Indicator calculations are numerically validated and historical price changes invalidate only affected stock/date ranges.
- API behavior is consistent with current routes and does not expose database implementation details.
- React detail views remain responsive and show missing/insufficient data honestly.

## Task 1: Baseline audit and shared domain contracts

**Files:** existing `portfolio-service/backend` models/repositories, `backend_api/app/market_data_routes.py`, `backend_api/app/main.py`, `migrations/alembic`, new service modules under `backend_api/app/services/market_data/`.

1. Confirm the actual table names/types for `stock_reference`, `stock_daily_prices`, `data_sources`, `ingestion_runs`, and `ingestion_errors`; document any differences between the pasted DDL and the live Supabase schema.
2. Define typed internal contracts for daily metrics, fundamental observations, shareholding observations, technical requests, and technical responses.
3. Define one canonical JSONB parameter serializer (sorted keys, compact separators, numeric normalization) so equivalent configurations share the same technical cache key.
4. Define source precedence rules: provider value > calculated fallback for daily metrics, while revised provider fundamentals/shareholding values replace the same provider observation through UPSERT.

## Task 2: PostgreSQL migration for fundamentals and technical cache

**Files:** new Alembic revision under `migrations/alembic/versions/`, migration documentation under `docs/`.

1. Create `market_data.stock_daily_metrics` with composite PK `(stock_id, metric_date)`, NUMERIC fields for market cap, PE, PB, dividend yield, book value, ROCE, and ROE, `calculation_method` (`PROVIDER`/`CALCULATED`), nullable `source_id`, timestamps, and a source/provider-preservation constraint.
2. Create `market_data.fundamental_metric_reference` with UUID PK, unique `metric_code`, statement type (`PL`, `BS`, `CF`, `RATIOS`), unit, description, timestamps; seed the common metric catalog with stable codes and idempotent inserts.
3. Create `market_data.stock_fundamental_values` with stock/metric/source FKs, `reporting_period` (`QUARTERLY`/`ANNUAL`), period start/end, `reporting_basis` (`CONSOLIDATED`/`STANDALONE`), NUMERIC value, timestamps, and a unique key covering stock, metric, reporting period, basis, and period end.
4. Create `market_data.stock_shareholding_history` keyed by `(stock_id, period_end_date)` with nullable promoter/FII/DII/government/public percentages, nullable shareholder count, source FK, timestamps, and 0–100 checks for each percentage.
5. Create `market_data.stock_technical_indicators` with stock/date, indicator code, indicator period, normalized JSONB parameters, component, NUMERIC value, status (`CURRENT`/`STALE`/`PENDING`), calculated/created/updated timestamps, and a uniqueness definition equivalent to `(stock_id, trading_date, indicator_code, indicator_period, parameters, component)`.
6. Add only targeted indexes: stock/date for daily metrics and shareholding, stock/reporting period/end for fundamentals, metric/end for fundamentals, and stock/indicator/parameters/date for technical reads.
7. Reuse existing timestamp conventions/functions and add foreign keys to current tables rather than duplicate trigger functions.

## Task 3: Screener provider adapter and fundamental ingestion

**Files:** new `portfolio-service/backend/market_data/providers/screener.py`, new ingestion service/pipeline modules, tests under `tests/market_data/`.

1. Port the useful pieces from `/home/prasad/dev_home/projects/stock_platform/nivesh-server/pipeline/fundamental_scraper.py`: Screener consolidated URL construction, async-safe HTTP fetch via a worker thread, BeautifulSoup table parsing, `_safe_float`, period parsing, checksum generation, 3-second request delay, 30-second pause every 10 stocks, and per-stock failure isolation.
2. Implement the adapter against this repo's stock UUIDs and `screener_slug`/symbol fallback; resolve the configured `data_sources` row for Screener and never create a second provider registry.
3. Map Screener P&L, balance-sheet, and cash-flow labels to seeded `fundamental_metric_reference.metric_code` values. Keep unmapped labels in a structured ingestion warning/error record rather than silently dropping them.
4. Convert Screener annual/quarterly period headers into period start/end dates and `reporting_period`; preserve consolidated versus standalone based on the requested source/page configuration.
5. Map shareholding rows to canonical categories, preserve NULL for absent categories, and map shareholder counts only when supplied.
6. Upsert financial values and shareholding rows. Use source checksum/idempotency to skip unchanged payloads and update revised provider observations in place.
7. Run through the existing ETL lifecycle (`BasePipeline`, `start_etl_run`, `finish_etl_run`, `ingestion_errors`) and expose per-stock progress/results for CLI or manual API execution.
8. Add a dry-run/one-stock mode and explicit user-agent/rate-limit configuration so the pipeline can be tested without scraping the full universe.

## Task 4: Daily metrics ingestion and calculation fallback

**Files:** new `portfolio-service/backend/market_data/daily_metrics.py` (or equivalent service location), repository/upsert modules, tests.

1. Define the provider metric mapping and numeric normalization for market cap, PE, PB, dividend yield, book value, ROCE, and ROE.
2. Upsert provider observations with `calculation_method=PROVIDER` and source ID.
3. Implement narrowly scoped fallback calculations only when reliable inputs exist (latest regular close, EPS/book value/statement values, and valid denominators); leave unavailable metrics NULL.
4. Make the upsert conflict logic preserve a provider value when a calculated fallback arrives later, while allowing a later provider refresh to replace the provider observation.
5. Add ingestion status/count/error reporting through the existing ETL tables.

## Task 5: Technical indicator calculation and cache/invalidation service

**Files:** new `backend_api/app/services/technical_indicators.py`, `backend_api/app/repositories/technical_indicators.py`, tests under `tests/market_data/technical/`.

1. Implement pure chronological calculations for RSI(14, Wilder), SMA(20/50/100/200), EMA(9/12/20/26/50/100/200), MACD(12,26,9) (`VALUE`, `SIGNAL`, `HISTOGRAM`), and Bollinger Bands(20,2) (`UPPER`, `MIDDLE`, `LOWER`).
2. Define indicator request defaults and validate custom periods/parameters before querying or writing.
3. Fetch the minimum preceding price history needed for warm-up; calculate sequentially; return NULL/omit observations until enough data exists; persist only the requested output range.
4. Implement `ensure_indicators(stock_id, request)` to read cache rows, reuse only `CURRENT` rows, mark missing/stale work as `PENDING`, calculate, UPSERT, and return results.
5. Use the canonical JSONB serializer for cache keys and MACD/Bollinger component rows.
6. Implement historical-price invalidation in the existing price ingestion/application path: when a stock date is inserted or changed, mark technical rows for that stock from that date forward `STALE`; do not add database triggers in V1.
7. Ensure repeated requests produce no duplicates, update `calculated_at` only after successful calculation, and preserve partial results for insufficient history.

## Task 6: FastAPI service and endpoint integration

**Files:** `backend_api/app/market_data_routes.py`, new service/repository modules, `backend_api/app/main.py` only if router registration is needed.

Add endpoints following current response/error conventions:

- `GET /api/v1/market-data/stocks/{symbol}/metrics/daily` with optional date/date-range filters.
- `GET /api/v1/market-data/stocks/{symbol}/fundamentals` with annual/quarterly, reporting-basis, date, and metric filters.
- `GET /api/v1/market-data/stocks/{symbol}/shareholding` with date range.
- `GET /api/v1/market-data/stocks/{symbol}/technical-indicators` accepting indicator selection, custom configurations, date range, and cache/recalculation behavior.
- `POST /api/v1/market-data/stocks/{symbol}/technical-indicators/recalculate` for explicit invalidation/recalculation of selected configurations.
- Optional protected/manual ingestion endpoints or CLI commands for one-stock and batch Screener runs, reusing the same pipeline service.

Resolve symbols to stock UUIDs once, validate dates/periods/indicator parameters with Pydantic models, return stable DTOs, and translate missing stock/data into the project's existing HTTP errors.

## Task 7: React stock detail experience

**Files:** `frontend-react/src/` stock detail routes/components/API client/styles.

1. Extend the stock detail page with tabs or sections for price history, daily metrics, fundamentals, shareholding, and technical analysis.
2. Add line-chart history for stocks using the existing chart component; add optional volume and candlestick controls already used elsewhere.
3. Add technical indicator selectors/configuration (RSI, SMA, EMA, MACD, Bollinger), date-range controls, loading/error/insufficient-history states, and a recalculate action.
4. Render fundamentals and shareholding as readable period tables with consolidated/standalone and annual/quarterly filters; preserve NULL as “—”.
5. Keep the page responsive at the existing breakpoints and avoid exposing raw JSONB/database field names.
6. Add API client types and query serialization tests for omitted empty filters and custom indicator parameter JSON.

## Task 8: Verification, fixtures, and documentation

**Files:** `tests/`, `docs/`, `README.md`, pipeline runbook.

1. Add migration/database tests for FKs, enum/check constraints, NULL handling, unique keys, and UPSERT behavior.
2. Add daily metric precedence tests, fundamental revision/coexistence tests, and shareholding NULL/percentage validation tests.
3. Validate each indicator against trusted small datasets, including warm-up, missing dates, repeated requests, CURRENT reuse, STALE recalculation, timestamp updates, and historical-price invalidation.
4. Add Screener parser fixtures for normal values, commas, percentages, parentheses negatives, dashes/NM, missing sections, and revised checksums; mock HTTP and verify throttling/failure accounting without live scraping.
5. Run Alembic upgrade/downgrade checks against a disposable database, backend pytest, and the React production build.
6. Document environment variables, data-source setup, one-stock/batch ingestion commands, indicator API examples, cache semantics, and the fact that Screener ingestion must respect site terms/rate limits.

## Suggested execution order

1. Baseline audit/contracts
2. Migration and metric seed
3. Repository/service primitives
4. Screener and daily-metric ingestion
5. Technical calculations/cache/invalidation
6. API endpoints
7. React stock detail UI
8. Tests, migration verification, build, and runbook
