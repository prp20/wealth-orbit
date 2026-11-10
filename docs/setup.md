# Set up Wealth Orbit

The setup script takes a fresh clone to a running app. It installs the Python tools, writes `.env`, applies the Postgres schema, creates the local portfolio file, and builds the React UI.

## What you need

- A Postgres database that already exists. Supabase is a fine choice. The script does not create a cloud database.
- macOS, Linux, or Windows.
- Node.js 20 or newer. If it is missing, the script prints one install command and stops. It does not install Node for you.

Market research (funds, stocks, and index history) uses `DATABASE_URL`. The portfolio ledger never leaves the local SQLite file named by `PORTFOLIO_SQLITE_URL`.

## Create a Supabase database

1. Create a project at https://supabase.com/dashboard .
2. Open **Project Settings → Database**.
3. Under **Connection string**, choose the **URI** and **Session** mode (port **5432** on `*.pooler.supabase.com`).
4. Copy that URI into the setup prompt (or into `.env` as `DATABASE_URL`).

Do **not** use the direct host (`db.*.supabase.co`) or **Transaction** mode (port **6543**). Guided setup rejects those. If `sslmode` is missing, setup appends `sslmode=require` for Supabase URLs.

A non-Supabase Postgres URL is still accepted when `SELECT 1` succeeds (local or other hosted Postgres).

## Run it

From the repo root.

macOS and Linux:

```bash
./scripts/setup.sh
```

Windows, from Command Prompt or by double-clicking the file:

```bat
scripts\setup.bat
```

Both files only install `uv` (after you say yes) and Python 3.13, then run the same guide. Press Enter to accept a default shown in brackets.

If Node is missing or older than 20:

- Windows: `winget install OpenJS.NodeJS.LTS`
- macOS: `brew install node`
- Linux: install Node.js 20+ from https://nodejs.org/ (or use nvm / NodeSource). Do not rely on apt `nodejs` packages older than 20.

Install that, then run the setup script again.

## What each prompt does

1. **Postgres URL.** Required. The characters are hidden. The script prints Supabase session-pooler steps first. The URL must start with `postgres://` or `postgresql://`. Supabase direct and transaction-pooler URIs are rejected without connecting. The script runs `SELECT 1` before it writes `.env`. A bad URL is not saved, and the prompt is shown again. Connection failures print a short reason without echoing the URL.
2. **Local portfolio file.** Enter keeps `sqlite+aiosqlite:///./portfolio-service/portfolio.db`.
3. **Session secret.** Leave it blank and one is generated. It is written to `.env` and is not printed.
4. **Index seed.** Recommended. Loads about five years of index history, which is what Home shows. It does not download the full history.
5. **Stock and fund names.** Off unless you say yes. A yes loads names only, up to a limit you choose (default 50). Prices and NAV are large and can be synced later from the UI.
6. **Order-history workbook.** Optional. A blank line skips it. A path imports that workbook in append mode.
7. **Start now.** Recommended. Starts the API on http://127.0.0.1:8000/ui/ . The first visit should be **Create an account**. That account is empty until a workbook is imported.

On macOS and Linux the `.env` file is readable only by your user.

## Start it later

From the repo root, with `.env` already in place:

```bash
uv run uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ui/ .

## Run setup again

Run the same script. It keeps the existing `.env` unless you say you want to reconfigure it. Stored passwords and the session secret are not printed. Schema updates, the local tables, and the UI build run again.

## India masters universe

Masters are identity rows (names/codes), not full market history.

| Domain | CSV under `data/seed/` | Size (approx) | Natural key |
|--------|------------------------|---------------|-------------|
| Stocks | `stocks.csv` equities | ~500 NSE names | `(exchange, trading_symbol)` |
| Stock sectors / industries | derived from `stocks.csv` | as listed in CSV | `(sector_name)`; `(sector_id, industry_name)` |
| Funds | `new_equity_only_updated.csv` | ~280 equity schemes | `scheme_code` |
| Fund AMCs / categories | derived from fund CSV | as listed in CSV | `(amc_name)`; category/subcategory pair |
| Indexes | `indices.csv` | ~12 | `index_code` |

Guided setup defaults stay small: recommended index history is about **5y** for Home; optional stock/fund seed is **names only** with a default limit of **50** (`--skip-prices` / `--skip-nav`). Full `max` OHLC/NAV/statements for every symbol is **not** part of install — open a symbol and use **Update** sync buttons (or API sync jobs) afterward.

Re-running masters seed upserts on those natural keys and must not create duplicate companies or schemes.

## Track beyond seed (India-first)

Use the UI **Add** control on Stocks / Mutual funds (and **Add index** on Home) when a name is not in the seed catalog. The API resolves one instrument, upserts the master on the same natural keys as seed, then enqueues minimal history (`prices` / `nav` / index history).

| Instrument | Identifier | Notes |
|------------|------------|-------|
| Stock | NSE `trading_symbol` | Runtime Yahoo ticker is `{symbol}.NS` |
| Mutual fund | AMFI `scheme_code` | Digits from MFAPI / mftool |
| Index | `index_code` + Yahoo `yf_symbol` | Allowlisted India codes can omit Yahoo; others require an explicit India Yahoo symbol |

Non-goals: US tickers, bulk exchange import, watchlists. Seed CLI remains the bulk path; the UI is single-instrument add. Re-adding an already-tracked code is idempotent (`status: existing`).

```bash
# Optional API (same behavior as the Add dialog)
curl -X POST "$API/market-data/instruments/stocks?enqueue_history=true" \
  -H 'Content-Type: application/json' \
  -d '{"trading_symbol":"RELIANCE"}'
```

## Seed flags

Reference CSVs live under `data/seed/`. With `DATABASE_URL` set:

```bash
# Indexes: masters + ~5y history for Home
uv run python portfolio-service/scripts/seed/run_seed_indexes.py --data-dir data/seed --index-period 5y

# Masters only (no OHLC / NAV) — matches guided setup
uv run python portfolio-service/scripts/seed/run_seed_stocks.py --data-dir data/seed --skip-prices --limit 50
uv run python portfolio-service/scripts/seed/run_seed_funds.py --data-dir data/seed --skip-nav --limit 50

# Optional capped masters + matching history/fundamentals (same CSV-order universe)
uv run python portfolio-service/scripts/seed/run_seed_stocks.py --data-dir data/seed --limit 20
uv run python portfolio-service/scripts/seed/run_seed_stocks.py --with-fundamentals --limit 5
uv run python portfolio-service/scripts/seed/run_seed_funds.py --data-dir data/seed --limit 10

# Orchestrator: prefer skips/limits — bare run loads full masters + OHLC/NAV (indexes default max)
uv run python portfolio-service/scripts/seed/run_all_seeds.py --data-dir data/seed --skip-prices --skip-nav --limit 50
uv run python portfolio-service/scripts/seed/run_all_seeds.py --only stocks --limit 20
```

Useful flags: `--dry-run`, `--limit N` (caps masters **and** the matching history/NAV/fundamentals universe on `run_seed_*` and `run_all_seeds`), `--price-period 5y`, `--index-period 5y`, `--skip-masters`, `--skip-prices`, `--skip-nav`. For stocks, `--with-fundamentals` is off unless you pass it. Avoid a bare `run_all_seeds.py` without skips/limits unless you intentionally want a full dump.

```bash
uv run python portfolio-service/scripts/load_reference_data.py --data-dir data/seed
uv run python portfolio-service/scripts/sync_yfinance.py --period 5y
```

## Import a workbook later

```bash
uv run python portfolio-service/scripts/import_transactions.py /path/to/Mutual_Funds_Order_History.xlsx --mode append
```

`--mode append` skips source rows that were already imported. `--mode update` rebuilds that file's transactions and holdings when the same export has corrections. A redemption for units bought before the report window is stored as an opening balance so the holding does not go negative.

The importer classifies short-term, ultra-short-term, liquid, money-market, corporate-bond, and gilt funds as debt. Other imported mutual funds are classified as equity. Those labels can be corrected later.

## Forgotten password

There is no password-reset email. The account lives in the local SQLite file. Clear `password_hash` for that user:

```bash
sqlite3 portfolio-service/portfolio.db "UPDATE users SET password_hash = NULL WHERE full_name = 'Your Name';"
```

Sign-up refuses a name that is already stored. Use another name, or remove that user from the file before creating the account again.
