# Release backlog files

Small, **single-outcome** releases after MVP 1.1.  
**One catalog row = one file.** Do not club multiple versions into one release document.

## How this works

| Layer | Role | Editable? |
|-------|------|-----------|
| [Nivesh_Product_Requirements_and_Roadmap_v1.1.md](../Nivesh_Product_Requirements_and_Roadmap_v1.1.md) | MVP baseline | No |
| [Nivesh_Product_Requirements_and_Roadmap_v1.2.md](../Nivesh_Product_Requirements_and_Roadmap_v1.2.md) | Strategy + catalog through research train | Careful evolution |
| [superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md](../superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md) | Architecture evaluation + north-star decisions for **1.20+** | Careful evolution |
| `docs/releases/<version>-<slug>.md` | Locked scope for **one** ship | **Not after freeze** |
| GitHub milestone + issues | Execution status | Yes |

## Rules

1. **One outcome per file.** If two features can ship independently, they are two versions.  
2. **Validate then ship** before starting the next version.  
3. After `Approved for freeze`, do not rewrite scope or check boxes here.  
4. Scope changes → addendum file or the next version.  
5. Status only on GitHub (`1.2`, `1.3`, … milestones).  
6. Short Foundation checklist inside every file; **1.20+ files also carry locked decisions and agent planning instructions** for future plans.  
7. **No live trading** through **1.27** (and not in 1.2–1.19 either).  
8. **Buy/Hold/Avoid product policy:** refused through **1.19**; allowed from **1.23** **only** via Stance Engine contract (see 1.23 / 1.27). SEBI/advisory legal design remains out of band unless a future release says otherwise.

## Trains

### Phase 0 — Research foundation (1.2–1.19)

Honesty, setup/ops, discovery depth, portfolio math, Strategy Lab, glossary (1.11) + evidence chat that **refuses** buy/sell.

### Phase 1 — North star (1.20–1.27)

Modular monolith + free-tier storage policy, daily watchlists/morning inbox, then Stance L1→L4 (rules → portfolio overlay → strategy merge → LLM explain → agentic stance chat).

**Free-tier pressure priority (from architecture evaluation):** complete Tier A (1.21) + portfolio MTM (1.12) + watchlists (1.22) + Stance L1 (1.23) before finishing every Strategy Lab nicety / L2 if quota is tight.

## Catalog

| File | Ver | Status |
|------|-----|--------|
| [1.2-equity-data-honesty.md](1.2-equity-data-honesty.md) | 1.2 | Approved for freeze |
| [1.3-setup-supabase-pooler.md](1.3-setup-supabase-pooler.md) | 1.3 | Outline |
| [1.4-sync-observability.md](1.4-sync-observability.md) | 1.4 | Outline |
| [1.5-seed-masters-on-demand.md](1.5-seed-masters-on-demand.md) | 1.5 | Outline |
| [1.6-track-beyond-seed.md](1.6-track-beyond-seed.md) | 1.6 | Outline |
| [1.7-stock-screener.md](1.7-stock-screener.md) | 1.7 | Outline |
| [1.8-fund-manager-tenure.md](1.8-fund-manager-tenure.md) | 1.8 | Outline |
| [1.9-deeper-fundamentals.md](1.9-deeper-fundamentals.md) | 1.9 | Outline |
| [1.10-deeper-technicals.md](1.10-deeper-technicals.md) | 1.10 | Outline |
| [1.11-glossary-chatbot.md](1.11-glossary-chatbot.md) | 1.11 | Outline |
| [1.12-portfolio-daily-mtm.md](1.12-portfolio-daily-mtm.md) | 1.12 | Outline |
| [1.13-portfolio-reports.md](1.13-portfolio-reports.md) | 1.13 | Outline |
| [1.14-portfolio-xirr.md](1.14-portfolio-xirr.md) | 1.14 | Outline |
| [1.15-candlestick-patterns.md](1.15-candlestick-patterns.md) | 1.15 | Outline (chart patterns) |
| [1.16-indicator-strategies.md](1.16-indicator-strategies.md) | 1.16 | Outline |
| [1.17-py-strategy-plugins.md](1.17-py-strategy-plugins.md) | 1.17 | Outline |
| [1.18-strategy-backtesting.md](1.18-strategy-backtesting.md) | 1.18 | Outline |
| [1.19-agentic-research-chat.md](1.19-agentic-research-chat.md) | 1.19 | Outline |
| [1.20-modular-monolith-foundations.md](1.20-modular-monolith-foundations.md) | 1.20 | Outline (north star) |
| [1.21-storage-tiers-quota-guards.md](1.21-storage-tiers-quota-guards.md) | 1.21 | Outline (north star) |
| [1.22-watchlists-morning-inbox.md](1.22-watchlists-morning-inbox.md) | 1.22 | Outline (north star) |
| [1.23-stance-engine-l1.md](1.23-stance-engine-l1.md) | 1.23 | Outline (north star — policy pivot) |
| [1.24-stance-on-portfolio.md](1.24-stance-on-portfolio.md) | 1.24 | Outline (north star) |
| [1.25-stance-strategy-l2.md](1.25-stance-strategy-l2.md) | 1.25 | Outline (north star) |
| [1.26-stance-explain-l3.md](1.26-stance-explain-l3.md) | 1.26 | Outline (north star) |
| [1.27-agentic-stance-chat-l4.md](1.27-agentic-stance-chat-l4.md) | 1.27 | Outline (north star) |

**Later** (no file until frozen): Groww/Zerodha sync (not live orders), multi-country indexes, product update channel — see v1.2 §5–§6.

## Creating GitHub work

1. Create milestone matching the version (e.g. `1.20`).  
2. One issue per `- [ ]` foundation/backlog bullet in that file.  
3. Do not edit the frozen markdown when issues close.  
4. For 1.20+, also follow each file’s **Agent planning instructions** when drafting implementation plans.
