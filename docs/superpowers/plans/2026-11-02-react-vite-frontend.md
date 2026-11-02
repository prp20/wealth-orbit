# React Vite Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Streamlit client with a clean, responsive React + Vite application for portfolio management and market-data discovery.

**Architecture:** The frontend is a standalone `frontend-react/` project. It communicates only with the FastAPI backend through a typed API client and never connects directly to SQLite or Supabase. The UI is organized around a persistent shell with portfolio navigation and focused pages for overview, transactions, mutual funds, and stocks.

**Tech Stack:** React, TypeScript, Vite, React Router, TanStack Query, CSS modules or scoped CSS, Vitest, Testing Library.

**Spec:** `docs/superpowers/plans/2026-11-02-fastapi-backend.md` and the existing Wealth Orbit repository layout.

## Global Constraints

- Do not expose database credentials in browser code.
- The frontend calls only `/api/v1` FastAPI endpoints.
- Use Indian financial formatting with exactly two decimal places.
- Keep the UI replaceable and avoid backend-specific database assumptions.
- Preserve a clear distinction between portfolio data and reference data.

## Design Direction

- Deep navy shell with a restrained mint accent for a financial workspace feel.
- Neutral content canvas with high-contrast text and generous spacing.
- One prominent overview surface; supporting tables stay quiet and scannable.
- Sentence-case labels, concise copy, keyboard-visible focus, and responsive layouts.
- Shared components: sidebar, page header, metric card, data table, empty state, error state, and loading skeleton.

## Information Architecture

```text
/                         Portfolio overview
/transactions             Transaction history and entry
/mutual-funds             Supabase mutual-fund reference data
/stocks                   Supabase stock reference data
```

### Task 1: Scaffold the React project

**Files:**
- Create: `frontend-react/package.json`
- Create: `frontend-react/vite.config.ts`
- Create: `frontend-react/tsconfig.json`
- Create: `frontend-react/src/main.tsx`
- Create: `frontend-react/src/app/App.tsx`

Set up Vite, TypeScript, routing, test tooling, and an environment-based `VITE_API_BASE_URL`.

### Task 2: API client and shared data types

**Files:**
- Create: `frontend-react/src/api/client.ts`
- Create: `frontend-react/src/api/portfolio.ts`
- Create: `frontend-react/src/api/marketData.ts`
- Create: `frontend-react/src/types/api.ts`

Implement typed fetch functions for health, portfolios, holdings, transactions, mutual funds, stocks, and sectors. Normalize API errors into a user-readable error shape.

### Task 3: Application shell and navigation

**Files:**
- Create: `frontend-react/src/components/AppShell.tsx`
- Create: `frontend-react/src/components/Sidebar.tsx`
- Create: `frontend-react/src/components/PageHeader.tsx`
- Create: `frontend-react/src/styles/tokens.css`
- Create: `frontend-react/src/styles/global.css`

Build the responsive shell with portfolio selection, user identity, navigation links, active states, and mobile collapse behavior.

### Task 4: Portfolio overview

**Files:**
- Create: `frontend-react/src/pages/OverviewPage.tsx`
- Create: `frontend-react/src/components/MetricCard.tsx`
- Create: `frontend-react/src/components/HoldingsTable.tsx`

Show invested amount, equity, debt, asset count, current holdings, and an explicit unavailable-market-value state until pricing endpoints exist.

### Task 5: Transactions workflow

**Files:**
- Create: `frontend-react/src/pages/TransactionsPage.tsx`
- Create: `frontend-react/src/components/TransactionForm.tsx`
- Create: `frontend-react/src/components/TransactionsTable.tsx`

Add transaction history, buy/sell form validation, pending states, conflict handling for insufficient holdings, and success refresh.

### Task 6: Reference-data pages

**Files:**
- Create: `frontend-react/src/pages/MutualFundsPage.tsx`
- Create: `frontend-react/src/pages/StocksPage.tsx`
- Create: `frontend-react/src/components/ReferenceTable.tsx`
- Create: `frontend-react/src/components/SearchToolbar.tsx`

Provide debounced search, category/sector filters, result counts, empty states, and accessible tables backed by Supabase API endpoints.

### Task 7: Tests and runbook

**Files:**
- Create: `frontend-react/src/**/*.test.tsx`
- Create: `frontend-react/README.md`
- Modify: `README.md`

Test routing, API error states, Indian number formatting, transaction validation, loading/empty states, and table filtering. Document startup and `VITE_API_BASE_URL` configuration.

## Verification

Run:

```bash
cd frontend-react
npm install
npm run test
npm run build
npm run dev
```

Expected result: tests pass, production build completes, and the app loads against the FastAPI backend at `VITE_API_BASE_URL`.
