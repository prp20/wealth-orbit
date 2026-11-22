# portfolio-service/backend

Domain layer for Wealth Orbit — **no HTTP**. Imported by `backend_api` and by CLIs under `portfolio-service/scripts/`.

## Packages

| Area | Path | Role |
|------|------|------|
| Ledger | `models.py`, `services.py`, `db.py` | Users, portfolios, transactions, weighted-average holdings |
| Market research | `market_data/` | Sync, providers (Yahoo, Screener, MF APIs), instrument registry, retention |
| Read models | `reference_service.py`, `reference_models.py` | Postgres queries for UI/API payloads |
| MF analytics | `mutual_fund_service.py`, `market_data/mutual_fund_*.py` | Fund metrics, holdings, overlap |
| Stock screens | `screen_plugins/` | Discover/validate/run plugins from `screens/` |
| Stock screening SQL | `market_data/stock_screen.py`, `screen_derived.py` | Screener snapshots |

## Scripts (sibling `../scripts/`)

Seeds, bulk sync, and workbook import — see [../../docs/setup.md](../../docs/setup.md) and [../../docs/data/README.md](../../docs/data/README.md).

## Tests

`pytest` modules under `tests/` exercise market data, screens, and portfolio rules against fixtures or test DB URLs.

## Docs

- [../../docs/data/portfolio.md](../../docs/data/portfolio.md)
- [../../docs/data/market.md](../../docs/data/market.md)
- [../../docs/architecture.md](../../docs/architecture.md)