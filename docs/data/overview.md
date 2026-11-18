# Data overview

Wealth Orbit deliberately splits **private portfolio state** from **shared market research**.

## Two stores

| Store | Connection | Schema / file | Typical size |
|-------|------------|---------------|--------------|
| Postgres | `DATABASE_URL` | `market_data` (Alembic under `migrations/`) | Cloud quota-bound (e.g. Supabase) |
| SQLite | `PORTFOLIO_SQLITE_URL` | Local `portfolio-service/portfolio.db` | Stays on your machine |

Never copy full OHLC/NAV history into SQLite. Portfolio endpoints only need asset identity links and ledger rows.

## What Postgres holds (research)

Aligned with [setup.md](../setup.md#storage-architecture):

**Persisted facts:** masters (stocks, funds, indexes, AMCs/categories), OHLC/NAV/index history (default **10y** windows), fundamentals (capped annual/quarterly periods), shareholding, latest Yahoo daily metrics, **latest trading day** technical indicators, sync job audit.

**Derived snapshots:** technicals recomputed from OHLC; Screener `sma_200` in SQL from stored prices.

## Tier posture (evaluation doc)

North-star storage policy (not all automation shipped):

| Tier | Intent | Examples |
|------|--------|----------|
| **S** | Always hot for daily use | Masters, latest metrics/technicals, user watchlists (when 1.22+ ships) |
| **A** | Hot history for core universe | ~10y OHLC/NAV for seeded names |
| **B** | On-demand or trimmed | `max` history, optional enrichment, old trim via `trim_market_history.py` |

See [../superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md](../superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md) for full tier design.

## Natural keys (idempotent sync)

Repeating seeds and syncs must upsert, not duplicate:

| Entity | Key |
|--------|-----|
| Stock | `(exchange, trading_symbol)` — NSE in practice |
| Mutual fund scheme | `scheme_code` (AMFI) |
| Index | `index_code` |
| Sector / industry | name pairs from seed CSV rules |

Details: [market.md](market.md).

## UI read path

React calls FastAPI `/api/v1/market-data/*` → `portfolio-service/backend/reference_service.py` and related modules → Postgres. Portfolio pages call `/api/v1/portfolios/*` → SQLite.