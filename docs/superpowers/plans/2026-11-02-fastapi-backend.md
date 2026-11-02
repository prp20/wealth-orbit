# FastAPI Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a FastAPI API that exposes local portfolio operations and Supabase market-data reference endpoints behind the shared frontend.

**Architecture:** One API application provides versioned HTTP routes. Portfolio routes use local SQLite through the existing backend service; market-data routes use the Supabase `market_data` schema through `DATABASE_URL`. The frontend will remain a separate client and will not own database access long term.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, psycopg2, SQLite, PostgreSQL/Supabase.

**Spec:** Existing Wealth Orbit repository layout and Supabase market_data DDL.

## Global Constraints

- Portfolio users, portfolios, assets, transactions, and holdings remain in local SQLite.
- Reference stocks, mutual funds, indexes, sectors, and industries are read from Supabase.
- Historical price and NAV tables are read-only API surfaces in V1; no ingestion is added here.
- No cross-database foreign keys.
- The shared frontend must remain replaceable.

## Review Focus

- Missing `DATABASE_URL` returns a clear service error instead of exposing credentials.
- Unknown portfolio IDs return HTTP 404.
- Soft-deleted users are not exposed by portfolio endpoints.
- Search and filters are parameterized and cannot alter SQL.
- Sell requests continue to use the existing atomic transaction rules.

### Task 1: API dependencies and application shell

**Files:**
- Modify: `pyproject.toml`
- Create: `backend-api/app/main.py`
- Create: `backend-api/app/dependencies.py`

Add FastAPI, Uvicorn, and HTTP test dependencies. Create `/api/v1/health` and mount routers.

### Task 2: Portfolio endpoints

**Files:**
- Create: `backend-api/app/portfolio_routes.py`
- Test: `tests/test_api.py`

Expose portfolio list, holdings, transaction history, and transaction creation. Use response models and HTTP 404/422 errors.

### Task 3: Market-data endpoints

**Files:**
- Create: `backend-api/app/market_data_routes.py`
- Modify: `portfolio-service/backend/reference_service.py`
- Test: `tests/test_api.py`

Expose mutual-fund, stock, index, sector, and industry reference lists with search/filter query parameters. Add optional daily history endpoints without changing data.

### Task 4: Runbook and frontend boundary

**Files:**
- Create: `backend-api/README.md`
- Modify: `README.md`

Document startup, endpoint groups, environment variables, and the migration path for the shared frontend to call the API.

### Task 5: Verification

Run Python compilation and API tests. Verify the route list and health endpoint locally.
