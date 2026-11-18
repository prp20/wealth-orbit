# Release catalog

Frozen milestone **outlines** for Wealth Orbit. These are product contracts and checklists — not every item is implemented on `main`.

**Handbook entry:** [../README.md](../README.md) · **Install truth:** [../setup.md](../setup.md) · **Architecture:** [../architecture.md](../architecture.md)

## Shipped train (foundation)

Outlines tied to research MVP work in this repo:

| Release | Topic |
|---------|--------|
| [1.2](1.2-equity-data-honesty.md) | Equity data honesty |
| [1.3](1.3-setup-supabase-pooler.md) | Supabase session pooler setup |
| [1.4](1.4-sync-observability.md) | Sync observability |
| [1.5](1.5-seed-masters-on-demand.md) | Seed masters on demand |
| [1.6](1.6-track-beyond-seed.md) | Track beyond seed (UI add instrument) |
| [1.7](1.7-stock-screener.md) | Stock screener plugins |
| [1.8](1.8-fund-manager-tenure.md) | Fund manager tenure |
| [1.9](1.9-deeper-fundamentals.md) | Deeper fundamentals |
| [1.10](1.10-deeper-technicals.md) | Deeper technicals |

## Portfolio & platform (outlines)

| Release | Topic |
|---------|--------|
| [1.12](1.12-portfolio-daily-mtm.md) | Daily mark-to-market |
| [1.13](1.13-portfolio-reports.md) | Portfolio reports |
| [1.14](1.14-portfolio-xirr.md) | XIRR |
| [1.15](1.15-candlestick-patterns.md) | Candlestick patterns |
| [1.16](1.16-indicator-strategies.md) | Indicator strategies |
| [1.17](1.17-py-strategy-plugins.md) | Python strategy plugins |
| [1.18](1.18-strategy-backtesting.md) | Strategy backtesting |
| [1.19](1.19-agentic-research-chat.md) | Agentic research chat |
| [1.20](1.20-modular-monolith-foundations.md) | Modular monolith foundations |

## Storage, inbox, stance, agentic (outlines)

| Release | Topic |
|---------|--------|
| [1.21](1.21-storage-tiers-quota-guards.md) | Storage tiers & quota guards |
| [1.22](1.22-watchlists-morning-inbox.md) | Watchlists & morning inbox |
| [1.23](1.23-stance-engine-l1.md) | Stance engine L1 |
| [1.24](1.24-stance-on-portfolio.md) | Stance on portfolio |
| [1.25](1.25-stance-strategy-l2.md) | Stance strategy L2 |
| [1.26](1.26-stance-explain-l3.md) | Stance explain L3 |
| [1.27](1.27-agentic-stance-chat-l4.md) | Agentic stance chat L4 |

## Glossary milestone

Release **1.11** (glossary chatbot) is referenced across stance/agentic docs but **no `1.11-*.md` file** is checked in yet. Treat glossary as **planned** until an outline file appears and code registers glossary routes.

## How to use these docs

- Implement against `setup.md` and code first — releases may lag or lead code slightly.
- Parent PRD: [Nivesh_Product_Requirements_and_Roadmap_v1.1.md](../Nivesh_Product_Requirements_and_Roadmap_v1.1.md)
- Deep architecture north star: [superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md](../superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md)