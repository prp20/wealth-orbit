# Mutual Fund Performance, Benchmark, and Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add persisted mutual-fund performance, benchmark comparison, risk ratios, and fund metadata while keeping NAV history compact and useful in the React detail page.

**Architecture:** Keep NAV/reference/analytics data in Supabase PostgreSQL under `market_data`; keep portfolio holdings and transactions in local SQLite. A provider layer fetches NAV, benchmark, and enrichment data; pure analytics functions calculate returns and risk; a queue worker persists snapshots; FastAPI exposes read-only DTOs and explicit sync jobs; React renders collapsed, independently refreshable sections.

**Tech Stack:** Python 3.13, FastAPI, psycopg2, PostgreSQL/Supabase, pandas/numpy-compatible calculations, mftool/AMFI, yfinance or existing index providers, React/Vite, TanStack Query.

**Spec:** This document is the source specification for the mutual-fund performance and enrichment work.

## Global Constraints

- NAV history must be stored once per scheme/date with a non-null source ID and positive NAV.
- Metrics must never persist NaN, infinity, or fabricated values; unavailable inputs produce `NULL` plus a completeness reason.
- Incremental sync uses a date watermark; force sync fetches the complete provider history and performs idempotent UPSERTs.
- GET endpoints read persisted data only; POST sync endpoints fetch/compute and persist data through the queue.
- Existing `/api/v1/market-data/mutual-funds/{scheme_code}` and `/history` routes remain compatible.
- All mutual-fund detail sections are collapsed by default.
- Daily NAV data is hidden inside the collapsed NAV-history section; users see the chart and can expand the data table.

## Current Data Audit

| Requirement | Available now | Decision |
|---|---|---|
| Daily NAV history | `mutual_fund_nav_history(scheme_id, nav_date, nav, source_id)` | Reuse; add bounded history pagination/summary DTO. |
| Fund benchmark mapping | `mutual_fund_reference.benchmark_index_id` | Reuse; validate mappings and expose benchmark metadata. |
| Benchmark history | `index_reference` exists; `index_daily_history` is referenced by the design but not used by current services | Add/verify benchmark history schema and ingestion before benchmark metrics. |
| Current metrics | `compute_metrics` only returns current NAV, volatility, drawdown, and optional 1Y absolute return in memory | Replace with persisted period metrics snapshot. |
| Trailing returns | Not stored | Calculate from NAV observations at as-of date using 1Y/3Y/5Y/10Y lookback dates; persist. |
| Rolling returns | Not stored | Calculate rolling annualized windows across NAV dates; persist summary plus optional series. |
| Alpha/beta | No benchmark return series in service | Requires aligned fund and benchmark returns. |
| Sharpe/sortino/std dev | Only volatility exists; no risk-free-rate policy | Add explicit annualization and risk-free-rate configuration. |
| Yield to maturity | Not present for most mutual-fund categories | Only show when a debt-fund provider supplies YTM; never infer it from NAV. |
| Expense ratio, exit load, AUM | Not in `mutual_fund_reference` | Add enrichment table/provider. mftool itself does not provide these fields. |

## Metric Definitions

- **Trailing return:** `(NAV_asof / NAV_at_or_before(asof - period)) - 1`; display 1Y, 3Y, 5Y, and 10Y as percentages. If the lookback date is unavailable, use the nearest prior observation within a documented tolerance; otherwise return `NULL` and `insufficient_history`.
- **CAGR:** `(ending / starting)^(365.25 / elapsed_days) - 1`; use for periods of at least one year.
- **Rolling return:** For every eligible as-of NAV date, calculate the same annualized return over the preceding 1Y/3Y/5Y/10Y window. Persist summary fields (latest, minimum, maximum, median) and optionally a series table for charting.
- **Standard deviation:** Standard deviation of aligned periodic fund returns, annualized by `sqrt(252)` for daily observations; use the same frequency for benchmark and fund.
- **Sharpe:** `(annualized_return - annualized_risk_free_rate) / annualized_stddev`. Store the risk-free-rate assumption and as-of date.
- **Sortino:** `(annualized_return - annualized_risk_free_rate) / annualized_downside_deviation`, where downside deviation uses negative returns against the configured minimum acceptable return.
- **Beta:** `covariance(fund_returns, benchmark_returns) / variance(benchmark_returns)` on aligned dates.
- **Alpha:** CAPM annualized alpha: `fund_return - [risk_free + beta * (benchmark_return - risk_free)]`.
- **Benchmark comparison:** Persist benchmark code/name, benchmark as-of date, trailing returns, relative excess return, beta, alpha, tracking error, and data alignment counts.
- **YTM:** Provider-reported portfolio yield for debt schemes only; store value, as-of date, provider, and unit (`PERCENT`).

## Provider/Data Acquisition Decisions

1. **mftool/AMFI:** Use for scheme identity, current quote, and historical NAV. It does not supply expense ratio, exit load, AUM, or reliable benchmark time series.
2. **Benchmark/index provider:** Use mapped `index_reference` rows and the existing index/yfinance mapping to populate `index_daily_history`; record provider/source IDs and ticker mapping. A missing benchmark mapping is a valid “not available” state.
3. **Enrichment provider:** Implement a separate adapter based on the existing Nivesh reference logic (for example Kuvera/Captnemo where legally and operationally permitted). Store raw provider payload hashes/updated timestamps and normalize only fields actually present. Enrichment failure must not fail NAV sync.
4. **Debt YTM:** Accept only provider-reported YTM from the enrichment payload or an approved factsheet source. Do not calculate YTM from NAV.
5. **Data freshness:** Store `as_of_date`, `fetched_at`, `source_id`, and `provider_status` for every enrichment/metric record. UI displays “not available” and freshness when absent/stale.

## Review Focus

- A scheme with fewer than 1/3/5/10 years of NAV history must return explicit insufficient-history flags rather than zero returns.
- A scheme with no benchmark mapping/history must still show fund-only metrics and a clear benchmark-unavailable state.
- Non-trading-day lookbacks must select the nearest prior valid observation, not a future NAV.
- Missing or malformed provider fields (AUM, expense ratio, exit load, YTM) must be nullable and non-fatal.
- Re-running force and incremental jobs must not duplicate rows or change historical NAV dates unexpectedly.

### Task 1: Schema and lineage

**Files:**
- Create: `migrations/alembic/versions/006_mutual_fund_analytics.py`
- Modify: `portfolio-service/backend/reference_models.py`
- Create: `docs/mutual-fund-data-lineage.md` (extend current lineage)
- Test: `tests/market_data/test_mutual_fund_schema_contract.py`

- [ ] Add/verify `market_data.index_daily_history` keyed by `(index_id, history_date)` with value/source/timestamps.
- [ ] Add `market_data.mutual_fund_metric_snapshots` keyed by `(scheme_id, as_of_date, metric_period)` containing trailing/rolling returns, volatility, Sharpe, Sortino, alpha, beta, drawdown, completeness flags, risk-free rate, benchmark IDs, and calculation version.
- [ ] Add `market_data.mutual_fund_enrichment` keyed by `(scheme_id, as_of_date, source_id)` containing AUM, expense ratio, exit load, YTM, manager/rating fields, raw payload hash, and provider status.
- [ ] Add constraints for non-negative/percentage values and indexes for scheme/as-of lookup.
- [ ] Test migration columns, unique keys, and nullability using a fixture schema or introspection test.

### Task 2: Provider adapters and benchmark sync

**Files:**
- Create: `portfolio-service/backend/market_data/providers/mutual_funds.py`
- Create: `portfolio-service/backend/market_data/providers/benchmarks.py`
- Create: `portfolio-service/backend/market_data/providers/enrichment.py`
- Create: `portfolio-service/backend/market_data/mutual_fund_sync.py`
- Test: `tests/market_data/test_mutual_fund_providers.py`

- [ ] Normalize mftool historical NAV payloads into positive `date`/`Decimal` rows with retries and provider diagnostics.
- [ ] Fetch benchmark history using the mapped index provider; support missing mappings without failing the fund job.
- [ ] Normalize enrichment fields with provider-specific parsers and a non-fatal error result.
- [ ] Implement incremental and force UPSERTs with fetched/inserted/updated/skipped counts and latest dates.
- [ ] Test mftool JSON/DataFrame shapes, malformed values, benchmark absence, and enrichment partial responses using fixtures only.

### Task 3: Analytics engine

**Files:**
- Create: `portfolio-service/backend/market_data/mutual_fund_analytics.py`
- Modify: `portfolio-service/backend/mutual_fund_service.py`
- Test: `tests/market_data/test_mutual_fund_analytics.py`

- [ ] Implement pure functions for trailing, rolling, annualized risk, Sharpe, Sortino, drawdown, alpha, beta, tracking error, and excess returns.
- [ ] Align fund/benchmark observations by date and reject insufficient or duplicate inputs deterministically.
- [ ] Persist one metric snapshot per scheme/as-of/period and record completeness plus calculation version.
- [ ] Test known synthetic NAV/benchmark series, non-trading-day lookbacks, zero benchmark variance, missing benchmark, and insufficient history.

### Task 4: Queue and FastAPI contracts

**Files:**
- Modify: `backend_api/app/market_data_routes.py`
- Modify: `backend_api/app/sync_queue.py`
- Modify: `backend_api/app/portfolio_backend.py`
- Test: `tests/market_data/test_mutual_fund_api_contract.py`

- [ ] Add queue types `MF_BENCHMARK`, `MF_ENRICHMENT`, and `MF_METRICS`; route workers to real sync/analytics services.
- [ ] Add endpoints for metrics, benchmark details/comparison, enrichment, and bounded NAV history.
- [ ] Keep GETs read-only and return explicit `available`, `as_of_date`, `insufficient_history`, and `data_source` fields.
- [ ] Reject metric sync when required NAV/benchmark prerequisites are absent, or enqueue prerequisites in a documented dependency order.
- [ ] Test 404s, empty history, duplicate jobs, successful persistence, and explicit unavailable benchmark/enrichment responses.

### Task 5: React mutual-fund detail UI

**Files:**
- Modify: `frontend-react/src/app/App.tsx`
- Modify: `frontend-react/src/api.ts`
- Modify: `frontend-react/src/components/MarketChart.tsx`
- Modify: `frontend-react/src/extra.css`
- Test: `frontend-react` build and route smoke test

- [ ] Keep NAV history collapsed by default; show chart first and place the daily NAV table behind a nested “View daily NAV data” disclosure.
- [ ] Add collapsed sections for Performance, Rolling returns, Risk ratios, Benchmark comparison, and Fund facts.
- [ ] Display 1Y/3Y/5Y/10Y trailing and rolling returns with `—` plus an explanatory reason when unavailable.
- [ ] Display alpha, beta, Sharpe, Sortino, standard deviation, YTM, expense ratio, exit load, AUM, benchmark name, and freshness/source labels.
- [ ] Add per-section sync controls and refetch persisted data after terminal jobs.
- [ ] Build and verify direct refresh at `/ui/mutualfunds/{scheme_id}`.

### Task 6: Operational verification

**Files:**
- Modify: `docs/mutual-fund-data-lineage.md`
- Create: `docs/runbooks/mutual-fund-analytics.md`

- [ ] Document provider precedence, risk-free-rate configuration, annualization frequency, lookback tolerance, and missing-data semantics.
- [ ] Run a fixture scheme through force NAV, benchmark, enrichment, and metrics sync; verify persisted rows and queue results.
- [ ] Run incremental sync twice and verify the second run is up to date without duplicate rows.
- [ ] Run the React build and API contract tests before committing.

### Task 7: Groww TOTP authentication and index-history provider

**Files:**
- Create: `portfolio-service/backend/market_data/providers/groww_auth.py`
- Create: `portfolio-service/backend/market_data/providers/groww_indices.py`
- Create: `portfolio-service/backend/market_data/groww_sync.py`
- Modify: `portfolio-service/backend/reference_models.py`
- Modify: `backend_api/app/market_data_routes.py`
- Modify: `backend_api/app/portfolio_backend.py`
- Create: `migrations/alembic/versions/007_groww_index_provider.py`
- Test: `tests/market_data/test_groww_auth.py`
- Test: `tests/market_data/test_groww_indices.py`

**Groww contract verified during planning:** Groww's official API accepts a TOTP exchange at `POST /v1/token/api/access` using an API key plus `{ "key_type": "totp", "totp": "123456" }`; subsequent requests use a Bearer access token and `X-API-VERSION: 1.0`. The token expires daily, and the API requires the relevant Groww API subscription/approval. Historical candle data is available through the historical candle endpoint with `exchange`, `segment`, `trading_symbol`, time range, and interval parameters; daily candles are the intended index-history frequency. See the [Groww authentication documentation](https://groww.in/trade-api/docs/curl) and [historical-data documentation](https://groww.in/trade-api/docs/curl/historical-data).

- [ ] Add a `GrowwAuthProvider` that reads `GROWW_API_KEY` and a TOTP seed (`GROWW_TOTP_SECRET`) only from environment/secret-manager configuration; never store the seed, generated TOTP, or access token in PostgreSQL, SQLite, logs, queue results, or API responses.
- [ ] Generate the six-digit code with `pyotp.TOTP(secret).now()`, exchange it for an access token, cache the token in process memory with expiry, and use a per-process refresh lock so concurrent jobs do not issue duplicate token requests.
- [ ] Refresh on expiry/401 once, apply bounded retries for 429/5xx responses, and redact `Authorization`, API keys, TOTP values, and token payloads in centralized logs.
- [ ] Make the provider injectable so all tests use mocked HTTP responses; no live Groww calls in CI.
- [ ] Add a Groww source record and an index-provider mapping table/columns containing `index_id`, Groww exchange/segment, Groww trading symbol, source ID, active flag, and last successful sync date. Do not assume display names are valid Groww symbols; verify symbols through Groww instrument/master data before enabling a mapping.
- [ ] Implement daily index candle ingestion with date watermark and force mode. Normalize Groww candle arrays (`timestamp, open, high, low, close, volume`) into `market_data.index_daily_history`, preserving source and provider timestamps. Index volume may be null/zero and must not block price ingestion.
- [ ] Add queue type `INDEX_HISTORY` and sync endpoint/job status. Fund metric jobs must either enqueue the mapped benchmark job first or return an explicit `benchmark_pending` state; they must never silently compare against stale/missing data.

#### Initial benchmark mapping proposal

These are category-to-benchmark defaults, not hard-coded provider symbols. The implementation must persist the mapping and permit overrides per scheme:

| Fund category | Benchmark label | Expected TRI benchmark |
|---|---|---|
| Flexi Cap | NIFTY 500 TRI | `NIFTY_500_TRI` (Groww symbol to be verified) |
| Focused | NIFTY 500 TRI | `NIFTY_500_TRI` |
| Multi Cap | NIFTY 500 Multicap 50:25:25 TRI | `NIFTY_500_MULTICAP_50_25_25_TRI` |
| ELSS | NIFTY 500 TRI | `NIFTY_500_TRI` |
| Large & Mid Cap | NIFTY LargeMidcap 250 TRI | `NIFTY_LARGEMIDCAP_250_TRI` |
| Broad large-cap reference | NIFTY 100 TRI | `NIFTY_100_TRI` |
| Mid-cap reference | NIFTY Midcap 150 TRI | `NIFTY_MIDCAP_150_TRI` |
| Small-cap reference | NIFTY Smallcap 250 TRI | `NIFTY_SMALLCAP_250_TRI` |

- [ ] Treat the user's category names (`FLEXI_CAP`, `FOCUSED`, `MULTI_CAP`, `ELSS`, `LARGE_MID_CAP`) as normalized classification keys, not Groww instruments.
- [ ] Resolve each benchmark's actual Groww `trading_symbol` via the instrument catalog or a reviewed configuration table; fail the mapping validation if a symbol is not found.
- [ ] Preserve the benchmark label and TRI/non-TRI identity in `index_reference`; never compare a fund against a price index when the intended benchmark is TRI.
- [ ] Add fixture tests for token refresh, redaction, candle normalization, 401 retry, rate-limit retry, missing-symbol rejection, watermark sync, and all eight initial mappings.

### Task 8: Groww-backed UI and benchmark diagnostics

**Files:**
- Modify: `frontend-react/src/api.ts`
- Modify: `frontend-react/src/app/App.tsx`
- Create/modify: `frontend-react/src/components/BenchmarkComparison.tsx`
- Test: `frontend-react` production build and API fixture tests

- [ ] Add an admin/operator-only benchmark sync control; do not expose API keys or TOTP controls to ordinary portfolio users.
- [ ] Display benchmark label, provider, latest benchmark date, fund/benchmark date overlap, and a clear stale/unavailable state.
- [ ] Show which category default was used and whether a scheme-specific benchmark override exists.
- [ ] Refetch performance metrics after benchmark sync succeeds and display `benchmark_pending`/`insufficient_history` as explanatory states rather than blank charts.
