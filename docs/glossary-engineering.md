# Engineering glossary

Contributor-facing terms. Distinct from a future investor glossary corpus (Varsity seed — release **1.11**, not implemented in API/UI on this branch).

## Product names

| Term | Meaning |
|------|---------|
| **Wealth Orbit** | Shipped product name (UI, API title) |
| **Nivesh** | PRD / codename in legacy docs and `nivesh_screens` package |

## Runtime

| Term | Meaning |
|------|---------|
| **Modular monolith** | Single FastAPI process + React static bundle; domain packages inside `portfolio-service/backend` |
| **Session pooler** | Supabase Postgres URI on port **5432** (`*.pooler.supabase.com`, Session mode) — required for `DATABASE_URL` |
| **Research open** | Most market-data GETs do not require login |
| **Legacy UI redirect** | Old top-level paths (`/stocks`, …) 307 to `/ui/...` |

## Data

| Term | Meaning |
|------|---------|
| **Natural key** | Upsert identity (e.g. `scheme_code`, `(exchange, trading_symbol)`) — repeats must not duplicate rows |
| **Dual store** | SQLite ledger + Postgres research — see [data/overview.md](data/overview.md) |
| **Tier S / A / B** | Hot/warm/trim storage policy from architecture evaluation — guides retention, not every guard is automated yet |
| **Latest-only technicals** | Indicators stored for the most recent trading day, not full series |
| **sync_jobs** | Postgres audit + in-process worker state for Yahoo/Screener/MF sync |

## Screens

| Term | Meaning |
|------|---------|
| **Screen plugin** | Python module under `screens/stock/` with `SCREEN_ID`, `SCREEN_META`, `screen()` |
| **Allowlisted snapshot** | DataFrame columns screen code may read — no live scrape at run time |
| **Refresh** | Rescan disk, validate plugins, update registry |

## Releases & stance (planned)

| Term | Meaning |
|------|---------|
| **Stance engine** | Future Buy/Hold/Avoid contract (releases **1.23–1.27**) — not in production code here |
| **1.11** | Planned glossary corpus + chat (Varsity) |
| **1.19** | Planned evidence-bound agentic chat (refuses trade advice until stance policy ships) |

## Future LLM env (when glossary agent lands)

Not used on this branch. Intended operator keys (placeholders only in `.env`):

| Variable | Purpose |
|----------|---------|
| `GROQ_API_KEY` | Groq inference for glossary agent chat |
| `GLOSSARY_LLM_MODEL` | Optional override; planned default **`openai/gpt-oss-120b`** (Groq free/dev; `llama-3.3-70b-versatile` retired) |

Deterministic seed glossary (no API key) is part of the **1.11** design — see release outlines, not current code.