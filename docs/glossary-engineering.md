# Engineering glossary

Contributor-facing terms. Distinct from the **investor** Glossary UI at `/ui/glossary` (release **1.11** — seed + optional local Varsity RAG).

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
| **main-flush** | Glossary route removes main padding so the chat fills the viewport |

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

## Glossary chat (1.11)

| Term | Meaning |
|------|---------|
| **Seed matcher** | Deterministic lookup over `glossary_seed.json` (`mode: fallback` / `POST /glossary/chat`) |
| **Seed agent** | LLM tool-calling over seed allowlist (`mode: agent`) |
| **Multi-agent RAG** | LangGraph Router→Retriever→Answerer→Critic over local Chroma index (`mode: multi_agent`) |
| **Browser sessions** | Multi-chat UI state in `localStorage` — not a server chat store |

Operator env (see [.env.example](../.env.example) and [setup.md](setup.md#glossary-chat-release-111)):

| Variable | Purpose |
|----------|---------|
| `GLOSSARY_LLM_PROVIDER` | `groq` (default) \| `openai` \| `openai_compatible` |
| `GLOSSARY_LLM_MODEL` | Model id (default **`openai/gpt-oss-120b`** on Groq) |
| `GLOSSARY_LLM_BASE_URL` | Required for `openai_compatible` |
| `GROQ_API_KEY` / `OPENAI_API_KEY` | Provider keys |

## Releases & stance (planned)

| Term | Meaning |
|------|---------|
| **Stance engine** | Future Buy/Hold/Avoid contract (releases **1.23–1.27**) — not in production code here |
| **1.19** | Planned evidence-bound agentic research chat (portfolio/market tools) — still refuses trade advice until stance policy ships |
