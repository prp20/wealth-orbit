# Portfolio ledger (SQLite + encrypted vault)

Private per-installation ledger. File path comes from `PORTFOLIO_SQLITE_URL` (default beside `portfolio-service/portfolio.db`).

**Multi-client path:** export the ledger to a JSON snapshot, AES-256-GCM encrypt it, and store only ciphertext in `public.portfolio_vault` (see [../design/portfolio-vault-crypto.md](../design/portfolio-vault-crypto.md)). PC helpers: `POST /api/v1/vault/push-from-sqlite`, CLI `portfolio-service/scripts/vault_migrate_push.py`, UI `/ui/vault`. Android decrypts the same row on device. Vault **reset is PC-only**.

## Core entities

- **User** — local account (`full_name`, password hash).
- **Portfolio** — one per user in current product shape.
- **Asset** — local identity for a held instrument (may reference external codes for MF/equity).
- **Transaction** — immutable buy/sell (and related types); drives holdings.
- **Holding** — aggregate `(portfolio_id, asset_id)` with quantity and cost basis.

SQLAlchemy models live in `portfolio-service/backend/models.py`. HTTP access: `backend_api/app/portfolio_routes.py`.

## Weighted average cost

`portfolio-service/backend/services.py` applies transactions under row lock:

- **Buy** — increases quantity and total cost.
- **Sell** — decreases quantity and removes proportional cost.
- **Zero position** — holding row removed; transactions retained for audit.

Holdings can be rebuilt by replaying transactions in date/order sequence with the same formulas.

## Import path

Broker workbook ingest:

```bash
uv run python portfolio-service/scripts/import_transactions.py /path/to/workbook.xlsx --mode append
```

Classification heuristics for debt vs equity MF are documented in [setup.md](../setup.md#import-a-workbook-later).

## Auth boundary

All portfolio routes require a valid session cookie. Market research list/detail routes are mostly open; see [../api/overview.md](../api/overview.md).