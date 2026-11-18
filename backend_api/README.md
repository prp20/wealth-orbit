# backend_api

FastAPI HTTP shell for Wealth Orbit: auth cookies, portfolio routes, market-data routes, OpenAPI, and static React at `/ui/`.

## Run (repo root)

```bash
uv run uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000
```

Reload during development:

```bash
uv run uvicorn backend_api.app.main:app --reload --host 127.0.0.1 --port 8000
```

Setup script uses the same entrypoint after building `frontend-react/dist`.

## Routers

| Module | Prefix | Store |
|--------|--------|-------|
| `app/auth_routes.py` | `/api/v1/auth` | SQLite sessions |
| `app/portfolio_routes.py` | `/api/v1/portfolios` | SQLite ledger |
| `app/market_data_routes.py` | `/api/v1/market-data` | Postgres research |

Domain imports go through `app/portfolio_backend.py` (re-exports from `portfolio-service/backend`).

## Static UI

When `frontend-react/dist` exists, `main.py` mounts `/ui/` and serves the SPA fallback for client routes.

Legacy bookmarks (`/stocks`, `/portfolio`, …) redirect into `/ui`.

## Environment

See root `.env.example` and [../docs/setup.md](../docs/setup.md):

- `DATABASE_URL` — Postgres (session pooler on Supabase)
- `PORTFOLIO_SQLITE_URL` — local ledger
- `SESSION_SECRET` — cookie signing
- `EXCHANGE_RATE_API_KEY` — optional Home USD/INR

## API map

[../docs/api/overview.md](../docs/api/overview.md) · live OpenAPI at `/docs`