# Nivesh --- Investment Research, Intelligence & Portfolio Platform

**Product Requirements Document (PRD) and post-MVP release roadmap**  
**Market:** India (primary); other markets only in later releases  
**Asset classes:** Mutual Funds and Listed Equities  
**Audience:** Personal investors initially; public multi-user platform over time  
**Product positioning:** Research-first retail-investor research and portfolio intelligence  
**Document status:** Post-MVP strategy and release train  
**Version:** 1.2  
**Date:** 9 November 2026  
**Baseline:** [Nivesh_Product_Requirements_and_Roadmap_v1.1.md](Nivesh_Product_Requirements_and_Roadmap_v1.1.md) (unchanged MVP specification)

------------------------------------------------------------------------

## Document purpose

This document is the **post-MVP** product baseline. It:

- Declares the research MVP (**≈ product 1.1**) as **shipped**.
- Keeps the research-first pillar order from v1.1.
- Defines **Foundation / ops** rules that apply to every release.
- Replaces the open-ended phase calendar with a **versioned release train**.
- Points detailed module requirements (M01–M13) at **v1.1**; this file does not rewrite those sections.

Frozen per-release backlog files live under [releases/](releases/README.md). GitHub milestones and issues track execution status. Status is not rewritten into frozen release files.

------------------------------------------------------------------------

## 1. Product spine (unchanged)

Pillar order:

1. **Research** — funds and companies  
2. **Intelligence** — screeners, comparisons, signals  
3. **Portfolio** — local holdings, returns, exposure  
4. **Trading** — later; sync before live orders  

Product principles from v1.1 still apply: data accuracy before feature quantity; deterministic calculations; traceability; no personalized buy/sell recommendations as a core feature.

### Data split (locked)

| Data | Store | Notes |
|------|--------|--------|
| Portfolio ledger (users, holdings, transactions) | Local SQLite (`PORTFOLIO_SQLITE_URL`) | Never leaves the machine |
| Market research (funds, stocks, indexes, statements, NAV, OHLC) | Shared Postgres (`DATABASE_URL`, e.g. Supabase session pooler) | Fetched/synced into the portal |

Do not greenfield-replace this split. Improve logging, fetch, idempotent storage, and retrieval inside it.

### Seed and history policy (locked)

- **Masters / identity** may be seeded for a defined India universe (schemes, companies, index codes).
- **Heavy history** (NAV, prices, statements, holdings) is filled **on demand** when the user opens or syncs a symbol, using upserts so re-sync does not duplicate rows.
- Setup may still offer a small recommended seed (indexes + limited masters), as in the guided installer.

------------------------------------------------------------------------

## 2. MVP 1.1 — shipped

The following are in the product and are treated as **done** for planning purposes. Remaining gaps become release backlog, not a reopen of “is MVP done?”

| Area | Shipped capability |
|------|--------------------|
| Setup | `scripts/setup.sh`, `scripts/setup.bat`, shared `setup_guide.py`, `.env.example`, [setup.md](setup.md) |
| Auth | Local sign-up / sign-in; portfolio gated; research open |
| Home (M01) | Major index tiles, delayed as-of, invested cost summary, recent research |
| Mutual funds (M02) | List, fund screener, compare, detail tabs, NAV, performance/risk snapshots, holdings, overlap, managers |
| Equities (M03) | List, detail tabs, OHLCV chart, fundamentals/statements/valuation/technicals snapshots, peers, shareholding |
| Portfolio | Workbook import, cost-based holdings, transactions; ledger in SQLite |
| APIs | FastAPI + React UI at `/ui/` |

Detailed acceptance language and module checklists remain in **v1.1**. Known honesty and completeness gaps (for example stock screener, watchlists, corporate-action-adjusted prices, equity statement tagging) are scheduled under **Release 1.2** and later — not as a reason to un-ship MVP.

------------------------------------------------------------------------

## 3. Foundation / ops (every release)

A feature is not done if it leaves silent failures, duplicate market rows, or unbounded N+1 reads.

Required in **every** release:

1. **Error logging** — structured logs for sync and API failures (console and/or log file). Never log secrets or full connection strings.  
2. **Fetch jobs** — use the existing sync job queue; retry transient failures where safe; persist SUCCEEDED / FAILED / CANCELLED.  
3. **Idempotent writes** — NAV, OHLCV, statements, holdings, indexes, and metric snapshots use natural keys / `ON CONFLICT` so re-sync does not duplicate.  
4. **Missing vs zero** — do not invent zeros for missing valuation inputs (for example net debt when one side is absent).  
5. **Freshness** — research pages show as-of / source when data exists.  
6. **Efficient retrieval** — prefer batched queries for lists, peers, and screeners; add indexes when history grows.  
7. **Setup** — keep Windows / macOS / Linux installers working; improve Supabase **session pooler** guidance without creating a cloud project from the script.

------------------------------------------------------------------------

## 4. Release train (small, single-outcome ships)

**One release = one coherent, fully validated outcome.** Do not club multiple catalog rows into one release file.

```text
MVP 1.1 (shipped)
  → 1.2 honesty → 1.3 setup → 1.4 sync
  → 1.5 seed → 1.6 beyond seed → 1.7 screener → 1.8 managers
  → 1.9 deeper fundamentals → 1.10 deeper technicals → 1.11 glossary
  → 1.12 MTM → 1.13 reports → 1.14 XIRR
  → 1.15 patterns → 1.16 strategies → 1.17 plugins → 1.18 backtest
  → 1.19 agentic
  → Later (brokers sync, multi-country, app updates)
```

| Ver | Outcome | Backlog file |
|-----|---------|--------------|
| **1.2** | Equity statement/valuation honesty | [releases/1.2-equity-data-honesty.md](releases/1.2-equity-data-honesty.md) |
| **1.3** | Setup + Supabase session pooler | [releases/1.3-setup-supabase-pooler.md](releases/1.3-setup-supabase-pooler.md) |
| **1.4** | Sync logging and safe retry | [releases/1.4-sync-observability.md](releases/1.4-sync-observability.md) |
| **1.5** | India masters seed; history on demand | [releases/1.5-seed-masters-on-demand.md](releases/1.5-seed-masters-on-demand.md) |
| **1.6** | Track MF / stock / index beyond seed | [releases/1.6-track-beyond-seed.md](releases/1.6-track-beyond-seed.md) |
| **1.7** | Basic stock screener | [releases/1.7-stock-screener.md](releases/1.7-stock-screener.md) |
| **1.8** | Tenure-dated fund manager returns | [releases/1.8-fund-manager-tenure.md](releases/1.8-fund-manager-tenure.md) |
| **1.9** | Deeper fundamental analysis | [releases/1.9-deeper-fundamentals.md](releases/1.9-deeper-fundamentals.md) |
| **1.10** | Deeper technical analysis (tables) | [releases/1.10-deeper-technicals.md](releases/1.10-deeper-technicals.md) |
| **1.11** | Investing glossary chatbot | [releases/1.11-glossary-chatbot.md](releases/1.11-glossary-chatbot.md) |
| **1.12** | Portfolio daily MTM / change | [releases/1.12-portfolio-daily-mtm.md](releases/1.12-portfolio-daily-mtm.md) |
| **1.13** | Simple portfolio report | [releases/1.13-portfolio-reports.md](releases/1.13-portfolio-reports.md) |
| **1.14** | Portfolio XIRR | [releases/1.14-portfolio-xirr.md](releases/1.14-portfolio-xirr.md) |
| **1.15** | Chart / candlestick patterns (stored records) | [releases/1.15-candlestick-patterns.md](releases/1.15-candlestick-patterns.md) |
| **1.16** | Built-in RSI/BB/EMA/SMA strategies | [releases/1.16-indicator-strategies.md](releases/1.16-indicator-strategies.md) |
| **1.17** | Discoverable `.py` strategy plugins | [releases/1.17-py-strategy-plugins.md](releases/1.17-py-strategy-plugins.md) |
| **1.18** | Strategy backtesting engine | [releases/1.18-strategy-backtesting.md](releases/1.18-strategy-backtesting.md) |
| **1.19** | Agentic research chat (evidence-bound) | [releases/1.19-agentic-research-chat.md](releases/1.19-agentic-research-chat.md) |
| **Later** | Brokers sync, multi-country, app updates | Section 6 |

**Rules**

- Each release has its own `docs/releases/<version>-<slug>.md`. **Do not merge** adjacent versions into one file.  
- After approval, do not silently edit a frozen file; use an addendum or the next version.  
- GitHub **milestones** match the version (`1.2`, `1.3`, …). One issue per backlog bullet. Status only on GitHub.  
- A short Foundation checklist sits **inside** every small release.  
- Validate and ship one release before starting the next.  
- **No live trading** through 1.19. Brokers later = holdings/transaction sync only.

------------------------------------------------------------------------

## 5. Idea map (from product brainstorm)

Every brainstormed item is assigned exactly once.

| Idea | Release |
|------|---------|
| Seed data for each stock or mutual fund (masters + on-demand history) | **1.5** |
| Track new mutual funds, stocks, or indices beyond seed | **1.6** |
| Stock and mutual fund screeners (fund exists; add stock screener) | **1.7** |
| Mutual fund managers historical data (tenure-dated) | **1.8** |
| Startup script for Windows and Mac/Linux (polish + Supabase pooler) | **1.3** |
| Rerun / tighten data model (logging, dedup, retrieval) | **1.4** (+ Foundation every release); equity honesty in **1.2** |
| Detailed fundamental analysis | **1.9** |
| Detailed technical analysis | **1.10** |
| Portfolio tracking daily changes | **1.12** |
| Reports generation | **1.13** |
| Portfolio XIRR | **1.14** |
| Chart / candlestick pattern recognition | **1.15** |
| Trading strategies using RSI, BB, EMA, SMA | **1.16** |
| User adds a new strategy via `.py` file, discoverable in UI | **1.17** |
| Strategy engine with back-testing | **1.18** |
| Chatbot that explains investing concepts (curated Varsity-cited glossary seed) | **1.11** |
| Agentic AI / agentic chat grounded in stored data | **1.19** |
| Groww / Zerodha support (holdings/transaction sync only) | **Later** |
| Multi-country index fetching and pattern recognition (US, Singapore, UK, Japan) | **Later** |
| Update support (how users get new app versions) | **Later** |

------------------------------------------------------------------------

## 6. Release catalog (summaries)

Each row is one ship. Full bullets live in the linked file. **1.2** is approved for freeze; **1.3+** are outlines until the previous version ships.

| Ver | Exit (one sentence) |
|-----|---------------------|
| 1.2 | Statements and valuation no longer lie for one smoke symbol |
| 1.3 | Fresh clone reaches `.env` with a valid session-pooler URL |
| 1.4 | Operator can see why a sync failed and retry without duplicates |
| 1.5 | Masters load without dupes; history still on sync |
| 1.6 | User can add a non-seeded India MF, stock, or index and sync history |
| 1.7 | User can filter/sort stocks like funds |
| 1.8 | UI never attributes full-scheme history to a short manager tenure |
| 1.9 | Stock fundamentals show richer ratio groups/trends from stored statements |
| 1.10 | Technicals show additional indicator families as numbers/tables |
| 1.11 | User can ask for a term definition and get a clear glossary answer (Varsity-cited seed) |
| 1.12 | Home/Portfolio show gain with as-of, or honest empty |
| 1.13 | One exportable report from local holdings |
| 1.14 | XIRR shown only when cash flows suffice |
| 1.15 | Chart patterns listed for a symbol (doodles not required) |
| 1.16 | One indicator strategy run produces dated signals on stored history |
| 1.17 | Sample `.py` plugin appears and runs without crashing the app |
| 1.18 | One strategy backtest returns CAGR/drawdown with disclosed assumptions |
| 1.19 | Agentic chat cites stored metrics only; refuses buy/sell advice |

### Later (after 1.19)

Freeze a new `docs/releases/1.x-….md` before building.

- **Brokers:** Groww / Zerodha sync of holdings and transactions into the local ledger, source-tagged. **No live order placement.**  
- **Multi-country indexes** (US, Singapore, UK, Japan) and pattern recognition — after India research/ops are stable and licensing is explicit.  
- **Product update support** for distributing new versions of the local app.  
- Follow-ons: watchlists/alerts, saved screens, if not pulled into an earlier freeze.

------------------------------------------------------------------------

## 7. AI and advice guardrails (releases 1.11 glossary, 1.19 agentic)

When glossary and agentic chat land:

- Glossary chat (1.11) may explain investing terms only, using curated definitions from [docs/varsity_docs/glossary_seed.json](varsity_docs/glossary_seed.json) and citing Varsity chapter URLs where applicable.  
- Do **not** ship or paste Zerodha Varsity PDF/full-chapter text; PDFs under `docs/varsity_docs/` are local research copies only.  
- Agentic chat (1.19) may only explain or suggest **checks** using numbers already stored in the app, with citations.  
- AI must not invent financial figures.  
- AI must not give personalized buy, sell, or switch recommendations for a named scheme or stock.

------------------------------------------------------------------------

## 8. Relationship to v1.1

| Topic | Where to read |
|-------|----------------|
| Module requirements M01–M13 | v1.1 §4 |
| Original MVP must/exclude and acceptance | v1.1 §5 |
| Data sources and calculation standards | v1.1 §6–7 |
| Architecture and domain boundaries | v1.1 §8–9 |
| Original phase 0–6 narrative | v1.1 §10 (superseded for scheduling by this release train) |
| Testing and compliance | v1.1 §12–16 |

v1.1 remains the **MVP baseline** and must not be edited to track post-MVP status. This v1.2 file is the living strategy document for releases after MVP; per-release backlog files are frozen after approval.

------------------------------------------------------------------------

## 9. How work is tracked

1. Strategy and release map → this document (v1.2).  
2. Locked scope for a ship → `docs/releases/<version>-<name>.md` (frozen).  
3. Execution → GitHub milestone + issues (one issue per bullet).  
4. Do not mark “done” by editing a frozen release file.

See [releases/README.md](releases/README.md).
