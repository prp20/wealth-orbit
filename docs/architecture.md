# Architecture (shipped)

How Wealth Orbit runs today on a developer machine. Longer-term modular-monolith / stance-roadmap notes may live in local-only planning docs under `docs/superpowers/` (gitignored).

## Runtime summary

| Piece | Location | Notes |
|-------|----------|--------|
| HTTP API | `backend_api/app/main.py` | FastAPI, OpenAPI at `/docs` |
| UI | `frontend-react/dist` served at `/ui/` | Vite SPA; legacy paths redirect into `/ui` |
| Portfolio domain | `portfolio-service/backend/` | SQLAlchemy models, transaction engine, `reference_service` |
| Market sync | `portfolio-service/backend/market_data/` | Providers, sync jobs, instrument registry |
| Screen plugins | `screens/` + `portfolio-service/backend/screen_plugins/` | Discovery, validation, SQL snapshot |
| Seeds / CLIs | `portfolio-service/scripts/` | Postgres load, Yahoo/Screener/MFAPI paths |
| Legacy UI | `frontend/streamlit_app.py` | Optional Streamlit; not the daily product UI |

Placeholder directories at repo root (`market-data-service/`, `strategy-engine/`, etc.) are **empty** — naming only, not processes.

## Request flow

```mermaid
flowchart LR
  subgraph client [Browser]
    React["React SPA /ui/"]
  end
  subgraph api [backend_api]
    FastAPI["FastAPI /api/v1"]
    Static["StaticFiles /ui/"]
  end
  subgraph domain [portfolio-service/backend]
    Port["Portfolio + auth helpers"]
    Mkt["market_data + reference_service"]
    Scr["screen_plugins"]
  end
  subgraph stores [Stores]
    PG[("Postgres market_data")]
    SQL[("SQLite portfolio.db")]
  end
  React --> FastAPI
  React --> Static
  FastAPI --> Port
  FastAPI --> Mkt
  FastAPI --> Scr
  Port --> SQL
  Mkt --> PG
  Scr --> PG
```

- **Research reads** (most stock/MF list and detail endpoints) use `DATABASE_URL` and do not require login.
- **Portfolio writes** require a session cookie backed by SQLite.
- **Sync** runs in-process (thread pool + `sync_jobs` rows in Postgres); large batch work also has CLIs under `portfolio-service/scripts/`.

## Module boundaries (practical)

| Concern | Owns |
|---------|------|
| `backend_api` | Routing, auth cookie, static UI mount, thin orchestration |
| `portfolio-service/backend/services.py` | Holdings math, transaction application |
| `portfolio-service/backend/market_data/` | Ingestion, retention caps, instrument add |
| `portfolio-service/backend/screen_plugins/` | User screen lifecycle |
| `frontend-react` | Pages, React Query to `/api/v1` |
| `screens/stock/` | Operator-authored filter plugins |
| `migrations/` | Alembic revisions targeting Postgres only |

## Authentication

Local accounts in SQLite: signup/login set an HTTP-only cookie. There is no email reset flow; see [setup.md](setup.md#forgotten-password).

## What is not shipped yet

Future milestones (MTM/XIRR, watchlists, stance engine, glossary chat, strategy lab) are tracked in local-only `docs/releases/` when present. Until those land in the product, the UI remains **cost-basis portfolio** plus **stored market research** — no buy/sell stance layer in production code.

## Related docs

- [data/overview.md](data/overview.md) — dual database policy
- [api/overview.md](api/overview.md) — route groups
- [getting-started.md](getting-started.md) — bootstrap