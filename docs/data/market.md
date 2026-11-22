# Market data (Postgres)

Schema: `market_data` (apply with `alembic -c migrations/alembic.ini upgrade head` using `ALEMBIC_DATABASE_URL` or `DATABASE_URL`).

Domain code: `portfolio-service/backend/market_data/` and `reference_service.py`. HTTP: `backend_api/app/market_data_routes.py`.

## Masters (`data/seed/`)

CSV-driven identity loaded by scripts under `portfolio-service/scripts/seed/` and `load_reference_data.py`:

| Domain | Seed file | Natural key |
|--------|-----------|-------------|
| Stocks | `data/seed/stocks.csv` | `(exchange, trading_symbol)` |
| Funds | `data/seed/new_equity_only_updated.csv` | `scheme_code` |
| Indexes | `data/seed/indices.csv` | `index_code` |

Guided setup keeps first install small (names-only limits). Bulk history uses CLIs documented in [setup.md](../setup.md).

## Time series and caps

| Data | Source (typical) | Retention note |
|------|------------------|----------------|
| Stock OHLC | Yahoo (`yfinance`) | Default `10y`; optional `max` |
| MF NAV | MFAPI / mftool | Default `10y` |
| Index history | Seed + Yahoo where mapped | Home index strip |
| Fundamentals | Screener.in scrape | 5 annual + 6 quarterly periods |
| Shareholding | Screener | Latest snapshot |
| Daily metrics | Yahoo | Latest row |
| Technicals | Computed from OHLC | Latest trading day only |

## Sync jobs

`market_data.sync_jobs` tracks in-process work from API and scripts. Status endpoints under `/api/v1/market-data/sync/*` and per-symbol sync POST routes.

## Screen snapshots

Stock screener plugins filter a **stored** column snapshot (allowlisted fields). Plugins do not call live brokers at run time. Authoring: [../../screens/README.md](../../screens/README.md).

## Lineage deep dives

- [mutual-fund-lineage.md](mutual-fund-lineage.md)
- [equity-lineage.md](equity-lineage.md)