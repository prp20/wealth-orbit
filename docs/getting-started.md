# Getting started

Short path from clone to a signed-in session. For every prompt and seed flag, see [setup.md](setup.md).

## Checklist

### 1. Prerequisites

- macOS, Linux, or Windows
- **Node.js 20+** (setup checks; it does not install Node)
- **Python 3.13** via `uv` (setup can install `uv` after you confirm)
- An existing **Postgres** database (Supabase is typical)

### 2. Supabase connection string

1. Create a project at [supabase.com/dashboard](https://supabase.com/dashboard).
2. Open **Project Settings → Database → Connection string**.
3. Choose **URI** and **Session** mode — port **5432** on `*.pooler.supabase.com`.
4. Use that value as `DATABASE_URL` in setup (or paste into `.env`).

Do **not** use the direct host (`db.*.supabase.co`) or **Transaction** pooler (port **6543**). Guided setup rejects both. Add `sslmode=require` if missing on Supabase URLs.

Non-Supabase Postgres URLs work when `SELECT 1` succeeds.

### 3. Run setup

From the repo root:

```bash
./scripts/setup.sh
```

Windows: `scripts\setup.bat`

Accept defaults where reasonable; optional seeds can stay off on first run (see [setup.md](setup.md#what-each-prompt-does)).

### 4. Open the app

If setup started the API: [http://127.0.0.1:8000/ui/](http://127.0.0.1:8000/ui/)

Otherwise:

```bash
uv run uvicorn backend_api.app.main:app --host 127.0.0.1 --port 8000
```

Choose **Create an account** on first visit. Accounts live in local SQLite (`PORTFOLIO_SQLITE_URL`).

### 5. Optional environment (after setup)

Edit `.env` in the repo root. **Never commit** real secrets.

| Variable | Purpose |
|----------|---------|
| `EXCHANGE_RATE_API_KEY` | Home USD/INR via ExchangeRate-API ([signup](https://www.exchangerate-api.com/)). Without it, USD/INR on Home may fail when that path is used. |
| `SESSION_SECRET` | Cookie signing (generated on first setup if left blank) |

**Glossary / Groq:** There is no glossary HTTP API or Groq integration in application code on this branch. When glossary chat lands, expect optional `GROQ_API_KEY` and `GLOSSARY_LLM_MODEL` (planned default `openai/gpt-oss-120b` on Groq — see [glossary-engineering.md](glossary-engineering.md)).

### 6. Smoke test

1. Sign in after account creation.
2. Open **Home** — index strip loads when index seed ran.
3. Open **Stocks** or **Mutual funds** — list pages read Postgres masters.
4. Open API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — try `GET /api/v1/health`.
5. (Optional) Run tests: `uv run pytest` from repo root.

### 7. Next reading

- [setup.md](setup.md) — seeds, UI “Add instrument”, screen plugins, workbook import
- [architecture.md](architecture.md) — how UI, API, and databases connect
- [data/overview.md](data/overview.md) — dual-store rules