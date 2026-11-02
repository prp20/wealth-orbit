# Market Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add interactive stock and mutual-fund historical charts with line, volume, and stock-only candlestick views.

**Architecture:** FastAPI exposes normalized historical observations from Supabase. React owns chart presentation and view state. Line charts are available for both asset types; volume and candlesticks are available only for stocks because mutual-fund NAV history has no OHLCV fields.

**Tech Stack:** FastAPI, psycopg2, React, TypeScript, TanStack Query, Recharts for line/volume, lightweight-charts for stock candlesticks.

**Spec:** Supabase `market_data.stock_daily_prices`, `market_data.mutual_fund_nav_history`, and the existing React + FastAPI plans.

## Global Constraints

- Stock OHLCV data comes from `market_data.stock_daily_prices`.
- Mutual-fund line charts use `market_data.mutual_fund_nav_history`.
- Volume and candlestick modes are stock-only.
- Dates, prices, NAV, and volumes must be returned in API-safe numeric forms.
- No market value or investment recommendation is introduced by this feature.

## API design

```text
GET /api/v1/market-data/stocks/{symbol}/history?from_date=&to_date=
GET /api/v1/market-data/mutual-funds/{scheme_code}/history?from_date=&to_date=
```

Stock response fields: `date`, `open`, `high`, `low`, `close`, `volume`.

Mutual-fund response fields: `date`, `nav`.

### Task 1: Backend historical queries

**Files:**
- Modify: `portfolio-service/backend/reference_service.py`
- Modify: `backend_api/app/market_data_routes.py`
- Test: `tests/test_market_data_api.py`

Add parameterized date-range queries and stable ascending date ordering. Return 404 for unknown symbols or schemes and an empty list for known assets with no history.

### Task 2: React chart data client and chart components

**Files:**
- Modify: `frontend-react/package.json`
- Modify: `frontend-react/src/api.ts`
- Create: `frontend-react/src/components/MarketChart.tsx`
- Create: `frontend-react/src/components/ChartToolbar.tsx`

Add chart dependencies, typed history calls, chart-mode controls, date-range controls, and responsive chart containers. The toolbar must hide volume and candlestick choices for mutual funds.

### Task 3: Stock and mutual-fund detail integration

**Files:**
- Modify: `frontend-react/src/app/App.tsx`
- Modify: `frontend-react/src/extra.css`

Embed line charts in both detail pages. Embed stock volume and candlestick modes in stock details. Show loading, no-history, and API-error states.

### Task 4: Verification and runbook

**Files:**
- Modify: `frontend-react/README.md`
- Modify: `README.md`

Document chart behavior and historical data prerequisites. Run frontend build and backend tests.

## Review focus

- Date ranges are inclusive and ordered chronologically.
- Missing history is shown as an empty state, not a broken chart.
- Candlestick mode never appears for mutual funds.
- Volume values remain integers and are not formatted as currency.
- Chart requests are canceled or replaced safely when users change assets or ranges.
