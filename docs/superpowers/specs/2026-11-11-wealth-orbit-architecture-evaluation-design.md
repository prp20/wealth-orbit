# Wealth Orbit — Architecture Evaluation & Target Design

**Date:** 2026-11-11  
**Status:** Draft for stakeholder review (design approved in session; awaiting file sign-off)  
**Scope:** Product/tech evaluation only. Regulatory / SEBI compliance design is explicitly out of scope per stakeholder decision.  
**Code changes in this deliverable:** None. This document only.

---

## 1. Context and locked decisions

### 1.1 Original evaluation ask

Validate:

1. Application architecture  
2. Daily-scale usability  
3. Storage and retrieval of market and portfolio data  
4. Fit for free / minimal-cost Supabase PostgreSQL  
5. Upcoming features under `docs/releases/`  
6. Cost posture (prefer free; minimize spend)  
7. Fitness for beginners and experienced users  
8. Path to data + **purchase suggestions with reasoning**

### 1.2 North star (beyond release 1.19)

- Explicit **Buy / Hold / Avoid** (or equivalent) **with reasoning** for stocks and mutual funds.  
- Aimed at **both beginners and experienced** users.  
- Goes **beyond** the current 1.2–1.19 train (which refuses personalized buy/sell through 1.19).

### 1.3 Decisions locked in design review

| Topic | Decision |
|-------|----------|
| Audience | **Hybrid:** personal / household first; design so multi-user is possible later without a rewrite |
| Daily loops | **All four:** morning check; research with stance; screener + watchlists; learning / glossary → later agentic insights |
| Stance production | **All four layers, incremental:** rules → strategy/backtest signals → LLM explanation → hybrid/agentic narrative |
| Cost | Prefer **strict free (A)**; ceiling is **rare light paid bumps (B)** (e.g. brief Supabase upgrade or cheap LLM API) |
| Deliverable | Full package: current-state review + target architecture + remapped post-1.19 roadmap + validation against initial requirements |
| Regulation | **Out of scope** for this document; product/tech only |
| Research universe | Aim for **full seed universe hot at ~10y** where possible; use trim / light paid bump if quota hits — pursued via **tiered storage**, not “load everything on day one” |
| Structural approach | **Approach 3 — Modular monolith + hot/warm data policy** (not microservices split; not “deepen without boundaries”) |

### 1.4 Chosen approach (summary)

Stay a **single deployable** (FastAPI + React) with clear **internal modules** and a **dual-store** boundary (private ledger vs shared market research). Chase full-universe depth with **Tier S / A / B** persistence so free-tier disk does not block daily decision use.

---

## 2. Current-state verdict

### 2.1 What exists (fit for personal research MVP)

| Layer | Reality |
|-------|---------|
| Runtime | Local FastAPI monolith (`backend_api/app/main.py`) on loopback; React SPA at `/ui/`; API at `/api/v1` |
| Portfolio | SQLite (`PORTFOLIO_SQLITE_URL`): users, portfolios, holdings, transactions |
| Market research | Supabase Postgres `market_data` schema via `DATABASE_URL` (session pooler required) |
| Sync | In-process `ThreadPoolExecutor` + Postgres `sync_jobs`; CLI seeds under `portfolio-service/scripts/` |
| Discovery | MF screener/compare in React; stock screen plugins under `screens/` + `nivesh_screens` helpers |
| Providers | Free/scraped: yfinance, Screener.in, MFAPI/mftool, Groww/Kuvera, AMFI CSVs — monetary risk is mainly **Supabase disk**, not paid market APIs |
| Auth | Local cookie sessions; portfolio gated; most market reads ungated (“research open”) |

Placeholder packages (`market-data-service/`, `strategy-engine/`, `analytics/`, etc.) are **empty** — aspirational layout, not services.

Streamlit (`frontend/streamlit_app.py`) remains a **legacy** portfolio/import path; daily product UI is React.

### 2.2 What is strained vs north star

- **No Stance / buy-hold-avoid layer.** Releases 1.11 (glossary) and 1.19 (agentic) explicitly refuse buy/sell; agentic is “checks only.” North star requires a deliberate **post-1.19 product pivot**.  
- **Daily loops incomplete:** portfolio is **cost-only** (no MTM / XIRR / reports in UI); no watchlists/alerts; **no shipped glossary UI or API** (Varsity glossary planned release 1.11); no Strategy Lab UI.  
- **Architecture smells** that block clean multi-user-ready evolution: fat `reference_service.py` and thick market routes; sync coupled to API process; per-query `psycopg2.connect` (no app pool); README/Streamlit drift; empty “service” folders that imply a split that was never executed.  
- **Data policy tension:** setup docs push masters + on-demand history; operational practice also pushes large **10y** seeds — the primary free-tier failure mode.

### 2.3 Verdict

**Foundation is fit for personal India MF/equity research.**  
**Not yet fit** for daily decision loops or explicit stance-with-reasoning without new modules and a disciplined storage policy.  
**Do not** split into microservices for the personal-first phase.

---

## 3. Target architecture (modular monolith)

### 3.1 Principle

One process / one deployable for personal-first. **Hard module interfaces** so multi-user later can extract or retarget stores without rewriting domain logic.

### 3.2 Module map

```text
React UI (Morning | Research | Screener/Watchlist | Glossary/Agent)
        │
        ▼
FastAPI thin HTTP routes
        │
        ├── Portfolio          → SQLite (private)
        ├── MarketResearch     → Supabase market_data (shared)
        ├── StanceEngine       → reads Market (+ Portfolio context when user is signed in)
        ├── StrategyLab        → reads Market; local compute
        ├── AgenticChat        → reads Stance + Market (+ glossary)
        └── Sync/Ingestion     → writes market_data; retention/quota guards
```

| Module | Owns | Does not own |
|--------|------|----------------|
| **Portfolio** | users, txs, holdings, MTM, XIRR, reports, watchlists (user-scoped) | market masters, scraping |
| **Market Research** | instruments, OHLC/NAV, fundamentals, technicals, screen snapshots, MF metrics | buy/hold/avoid wording |
| **Stance Engine** | labels + evidence (rules first; later merge strategy/LLM adapters) | raw scraping |
| **Strategy Lab** | patterns, indicator strategies, plugins, backtests | portfolio ledger |
| **Agentic Chat** | glossary → evidence-bound chat that **reads** Stance/Market | inventing prices or a second scoring system |
| **Sync / Ingestion** | providers, jobs, retention, quota guards | UI decisions |

### 3.3 Multi-user readiness without rewrite

- **Shared:** market facts in Postgres `market_data`.  
- **Private:** user, portfolio, watchlists, stance history, chat threads in SQLite now → tenant Postgres (or equivalent) later with the **same schemas/contracts**.  
- Stance and portfolio APIs take `user_id` / portfolio context even in personal mode.

### 3.4 Explicit non-goals (this phase)

- No microservice split into the empty package directories.  
- No broker execution / live trading.  
- No TimescaleDB unless free-tier math later forces a storage technology change.  
- No SEBI/compliance architecture in this document.

---

## 4. Storage and retrieval (free-first + full-universe ambition)

### 4.1 Dual-store split (keep)

| Store | Role | Multi-user later |
|-------|------|------------------|
| **SQLite (private)** | users, portfolios, txs, holdings, watchlists, stance history, chat | migrate to tenant Postgres; same logical schemas |
| **Supabase `market_data` (shared)** | masters, series, fundamentals, technicals, MF metrics, sync jobs | stays shared read-mostly research DB |

### 4.2 Tiered persistence

Reconciles “full seed universe ~10y” with cost A→B:

| Tier | Content | Hot policy |
|------|---------|------------|
| **S — Masters** | Full seed stock/fund/index references (~500 / ~280 / ~12) | Always hot; cheap |
| **A — Screener / stance fuel** | Latest metrics, capped fundamentals (5 annual + 6 quarterly), latest technicals, MF metric snapshots | Always hot for **full universe** so screeners and L1 stance work without 10y bars for every symbol |
| **B — Deep history** | Daily OHLC / NAV toward 10y | Expand by priority: portfolio holdings → watchlist → recently viewed → opportunistic bulk backfill while under free quota |

**Guards (required):**

- Probe `pg_database_size` (or equivalent) before bulk seed.  
- Warn/refuse unbounded `max` history on free tier.  
- Keep retention cutoffs and `trim_market_history`.  
- Allow a **light paid bump (B)** only when Tier A is complete and Tier B backfill is blocked by quota.

**End state vs day-one:** same ambition as “full universe at 10y,” sequenced so the app stays usable. Full universe at **Tier A immediately**; full universe at **Tier B as quota allows**.

### 4.3 Retrieval rules

- Lists / screeners: indexed **latest snapshots** (Tier A) — no full-history table scans.  
- Charts / deep evidence: per-symbol date range on `(entity_id, date)` keys.  
- Screener stays one query over stored metrics, not live scrapes.  
- Replace per-call `psycopg2.connect` with a **small pooled** client through the **session pooler** (still free; fewer connection errors).

### 4.4 Free-tier judgment

| Risk | Severity | Mitigation in this design |
|------|----------|---------------------------|
| Disk from full 10y OHLC+NAV for entire seed | High | Tier B priority + trim + light B bump only if Tier A is complete and Tier B is quota-blocked |
| Screener needing all symbols | Medium | Tier A always-hot snapshots |
| Connection limits | Medium | App-side pool + session pooler |
| Paused project / read-only | Medium | Existing sync/seed read-only handling |
| Egress | Low for DB | Most download volume is provider→app |

---

## 5. Daily usability (four loops)

### 5.1 Loop map

| Loop | Beginner need | Experienced need | Today | In 1.2–1.19 | Still missing for north star |
|------|---------------|------------------|-------|-------------|------------------------------|
| **Morning (~5 min)** | Portfolio up/down, simple attention | MTM, concentration, stale sync, watchlist deltas | Cost-only portfolio; Home indexes + sync jobs | 1.12–1.14 MTM/reports/XIRR; 1.4 sync visibility | Watchlists + alerts; stance summary on holdings |
| **Research (15–30 min)** | Plain thesis + clear stance | Full fund/tech + evidence trail | Strong detail tabs; per-panel sync | 1.2, 1.8–1.10 depth/honesty | **Stance strip** on stock/fund detail |
| **Screen → shortlist** | Preset screens | Custom filters + plugins | MF screener; stock plugin screener (in progress) | 1.7 | Watchlists; save screen; stance column; stock compare |
| **Learn / chat** | In-context glossary | Agentic Q&A over facts + stance | Glossary seed only | 1.11 / 1.19 (refuse buy/sell) | After Stance: chat **presents** engine output (policy pivot) |

### 5.2 UX principles

- Every instrument page ends with a **Stance strip**: label + 3–7 evidence bullets + data as-of + missing-data honesty.  
- **One engine, two presentations:** Simple (beginner) vs Factor detail (expert).  
- Home becomes a **decision inbox**: MTM, watchlist changes, failed syncs, holdings with stance flips — not only index tiles.  
- **React-only** daily surface; move Streamlit portfolio import into React so the morning loop is not split across apps.

### 5.3 Usability verdict

Research browsing is already useful. **Daily decision use is not**, until MTM + watchlist + Stance exist. Chat ships **after** Stance so the agent explains a versioned scorecard instead of freelancing labels.

---

## 6. Stance / recommendation stack (L1→L4)

### 6.1 Composition rule

Later layers **compose**; they do not replace the Stance contract. LLM/agent **must not change the label** without re-running rules/merger.

```text
Tier A facts ──► L1 Rules scorecard ──┐
                                      ├──► Stance merger ──► Label + evidence
Market history ─► L2 Strategy signals ─┘         │
                                                 ├──► L3 LLM plain-language explain
                                                 └──► L4 Agentic chat (bound to Stance)
```

### 6.2 Layers

| Layer | Behavior | Cost | Gate |
|-------|----------|------|------|
| **L1 Rules** | Factor scores → Buy/Hold/Avoid (or Buy/Hold/Reduce/Avoid) + deterministic bullets + as-of/missing | Free | Tier A + equity honesty (1.2); ships as **1.23** |
| **L2 Strategy** | Built-in/plugin signals + backtest stats as evidence; user-selectable strategy-aligned mode alongside default house scorecard | Free (local compute) | After 1.14–1.17; ships as **1.25** |
| **L3 LLM explain** | Beginner prose from L1/L2 evidence; **label immutable**; feature off when no model is configured | Prefer free/local; else rare cheap API (B) | After L1 stable; ships as **1.26** |
| **L4 Agentic** | Chat retrieves facts + **current Stance**; explains and suggests checks; bound to engine | Same as L3 | After 1.11 glossary; **extends** 1.19 via policy pivot; ships as **1.27** |

### 6.3 Stance response contract

Every stance returns at least:

- `instrument_id`  
- `label`  
- `confidence`  
- `factors[]`  
- `evidence[]`  
- `as_of`  
- `missing[]`  
- `engine_version`  
- `strategy_context` when L2 mode is active (otherwise omitted)

### 6.4 Portfolio-aware overlay

Shipped in **1.24**: e.g. “Hold existing position / Avoid new buy” when concentration or cost-basis context exists — still rules-first, same contract.

### 6.5 Out of scope here

Live order routing; SEBI/advisory registration design.

---

## 7. Release remap

### 7.1 Phase 0 — Finish current train (1.2–1.19)

Keep the existing release docs as the research foundation:

| Band | Releases | Role |
|------|----------|------|
| Data & ops | 1.2–1.6 | Honesty, pooler, sync UX, masters, track-beyond-seed |
| Discovery & depth | 1.7–1.10 | Stock screener, manager tenure, deeper fund/tech |
| Portfolio daily | 1.12–1.14 | MTM, reports, XIRR |
| Strategy | 1.14–1.17 | Patterns → strategies → plugins → backtests (feeds L2) |
| Chat (constrained) | 1.11, 1.19 | Glossary + evidence chat that **refuses** buy/sell until Stance exists |

**Cross-cutting while finishing 1.7–1.13:** prefer not to invent parallel features; north-star structural work is captured as **1.20–1.22** (do not silently merge into frozen 1.2–1.19 files).

### 7.2 Phase 1 — Post-1.19 north star (release files under `docs/releases/`)

Numbering uses **1.20 onwards** (not 2.0) so the train stays continuous with Phase 0. Each row has a detailed release markdown with locked decisions and agent planning instructions.

| ID | File | Delivers |
|----|------|----------|
| **1.20** | [1.20-modular-monolith-foundations.md](../../releases/1.20-modular-monolith-foundations.md) | Modular monolith module boundaries; thin routes; no microservice split |
| **1.21** | [1.21-storage-tiers-quota-guards.md](../../releases/1.21-storage-tiers-quota-guards.md) | Tier S/A/B policy; quota probes; pooled session-pooler access; `max` refusal |
| **1.22** | [1.22-watchlists-morning-inbox.md](../../releases/1.22-watchlists-morning-inbox.md) | Watchlists; Home morning inbox; React-only daily import path; Tier B priority inputs |
| **1.23** | [1.23-stance-engine-l1.md](../../releases/1.23-stance-engine-l1.md) | Buy/hold/avoid L1 rules + evidence; stance strip; **policy pivot** |
| **1.24** | [1.24-stance-on-portfolio.md](../../releases/1.24-stance-on-portfolio.md) | Holding-level stance; new-buy vs hold-existing overlay |
| **1.25** | [1.25-stance-strategy-l2.md](../../releases/1.25-stance-strategy-l2.md) | Merge strategy/backtest signals; strategy-aligned mode |
| **1.26** | [1.26-stance-explain-l3.md](../../releases/1.26-stance-explain-l3.md) | LLM prose bound to engine; disabled if no model |
| **1.27** | [1.27-agentic-stance-chat-l4.md](../../releases/1.27-agentic-stance-chat-l4.md) | Agentic chat presents Stance; must not invent labels |

### 7.3 Policy pivot (product)

- Through **1.19**, behavior matches current docs: no buy/sell recommendations.  
- When **1.23** ships, PRD language “never buy/sell” is **replaced** by: stance **only** via the Stance Engine contract (deterministic label path; LLM/agent may explain, not override). See release 1.27 for chat supersession of 1.19 on stance questions.

### 7.4 Priority under free-tier pressure

If disk/quota pressure spikes, prioritize:

1. **1.21** Tier A complete for the seed universe  
2. **1.12** (MTM)  
3. **1.22** (watchlists / morning inbox)  
4. **1.23** (Stance L1)  

…before finishing every Strategy Lab nicety in 1.14–1.17 / **1.25**. Those items unlock daily decision use under cost A→B.

---

## 8. Validation matrix (initial requirements)

| Requirement | Verdict | Notes |
|-------------|---------|-------|
| Application architecture | **Partial → target defined** | Monolith + dual DB is sound for personal MVP; needs modular boundaries + Stance/Sync clarity (Approach 3) |
| Daily usability | **Fail today / path defined** | Research OK; morning/decision loops need MTM, watchlists, Stance, React-only import |
| Storage & retrieval | **Partial** | Schema and retention design are good; full 10y bulk seed fights free tier; Tier S/A/B is the fix |
| Free Supabase Postgres | **Conditional pass** | Viable with Tier A-first + Tier B priority + trim; unsafe if unconstrained full-universe 10y OHLC day one |
| Upcoming features (`docs/releases/`) | **Aligned as foundation** | 1.2–1.19 remain valid research spine; do not deliver north-star buy/sell inside 1.11 glossary / 1.19 agentic |
| Minimal cost | **Aligned with caveats** | Prefer A; B only for quota or explanation UX; avoid paid market-data dependency for MVP stance |
| Beginner + experienced | **Partial** | Detail pages favor experienced; beginners need Simple stance + glossary/chat after L1 |
| Purchase suggestions + reasoning | **Not in current train; designed as 1.23–1.27** (after 1.20–1.22 foundations) | Explicit post-1.19 Stance stack in `docs/releases/` |

---

## 9. Spec self-review checklist

Completed at authoring time:

- [x] No TBD / TODO placeholders left in normative sections  
- [x] No contradiction between “refuse buy/sell through 1.19” and “north star buy/hold/avoid” (sequenced via policy pivot at 1.23)  
- [x] Universe “full 10y” ambition reconciled with free tier via Tier S/A/B (not two conflicting day-one policies)  
- [x] Scope limited to evaluation + target design + roadmap remap; no implementation tasks claimed done  
- [x] SEBI called out as out of scope consistently  
- [x] Microservices explicitly deferred  

---

## 10. Next step after stakeholder file review

When this file is approved:

1. Invoke **writing-plans** only for the next agreed slice (recommended first: **1.20** modular foundations or **1.21** Tier A/quota — **not** all of 1.20–1.27 at once).  
2. Do **not** edit frozen `docs/releases/1.2`–`1.19` outcome text except via the project’s normal release process; Phase 1 files **1.20–1.27** already live under `docs/releases/`.  
3. No application code until an implementation plan is explicitly approved for one milestone.

---

## 11. Key references

- `docs/releases/` (1.2–1.27 and README)  
- `docs/Nivesh_Product_Requirements_and_Roadmap_v1.2.md`  
- `docs/Nivesh_Product_Requirements_and_Roadmap_v1.1.md`  
- `docs/setup.md`  
- `backend_api/app/main.py`  
- `backend_api/app/sync_queue.py`  
- `portfolio-service/backend/reference_service.py`  
- `portfolio-service/backend/market_data/`  
- `frontend-react/src/app/App.tsx`  
- `screens/`, `nivesh_screens/`  
- `migrations/alembic/versions/`  
