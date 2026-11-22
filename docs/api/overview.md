# API overview

Base URL (local): `http://127.0.0.1:8000`

- **OpenAPI UI:** `/docs`
- **JSON schema:** `/openapi.json`
- **Health:** `GET /api/v1/health`

Routers are mounted in `backend_api/app/main.py`.

## Auth (`/api/v1/auth`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/auth/status` | No | Session probe |
| GET | `/auth/me` | Cookie | Current user + portfolio id |
| POST | `/auth/signup` | No | Create local account |
| POST | `/auth/login` | No | Session cookie |
| POST | `/auth/logout` | Cookie | Clear session |

## Portfolios (`/api/v1/portfolios`)

Requires session cookie unless noted.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/portfolios` | List portfolios for user |
| GET | `/portfolios/{id}/holdings` | Holdings with cost |
| GET | `/portfolios/{id}/transactions` | Ledger |
| POST | `/portfolios/{id}/transactions` | Add transaction |

## Market data (`/api/v1/market-data`)

Most read routes are **ungated** (research open). Screen refresh/run and some sync POSTs require auth.

### Sync & jobs

- `GET /market-data/sync/queue`
- `GET /market-data/sync/jobs/{job_id}`
- Stock / MF per-symbol sync POST + status routes

### Instruments (add / preview)

- `GET/POST /market-data/instruments/stocks`
- `GET/POST /market-data/instruments/mutual-funds`
- `GET/POST/PATCH /market-data/instruments/indexes`

### Mutual funds

List, screen, compare, detail, NAV/metrics/benchmark/holdings/managers, history, enrichment, overlap, and typed sync POSTs under `/market-data/mutual-funds/*`.

### Stocks

List, screen, compare, detail, peers, valuation, fundamentals, shareholding, technicals, history, and sync under `/market-data/stocks/*`.

### Stock screens

- `GET /market-data/stocks/screens`
- `POST /market-data/stocks/screens/refresh`
- `POST /market-data/stocks/screens/{screen_id}/run`

### Indexes & FX

- `GET /market-data/benchmarks`, summary, history
- `POST /market-data/benchmarks/sync` (+ status)
- `GET /market-data/fx/usd-inr`

### Filters

- `GET /market-data/filters/{kind}`
- `GET /market-data/sectors`

## Static UI

- React build: `/ui/` (also legacy redirects from `/stocks`, `/mutualfunds`, etc.)

## Implementation map

| Router file | Prefix |
|-------------|--------|
| `auth_routes.py` | `/api/v1/auth` |
| `portfolio_routes.py` | `/api/v1/portfolios` |
| `market_data_routes.py` | `/api/v1/market-data` |

Domain logic: `portfolio-service/backend/` (imported via `backend_api.app.portfolio_backend`).

## Glossary API

Public (no session) under `/api/v1/glossary` — see [../setup.md](../setup.md#glossary-chat-release-111):

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/chat` | Single-turn seed matcher |
| `POST` | `/agent/chat` | Multi-turn Groq tool agent (falls back to matcher) |
| `GET` | `/terms` | Browse curated seed terms |