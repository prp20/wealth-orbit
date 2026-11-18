# Wealth Orbit documentation

Handbook for contributors and operators. Product name in the UI is **Wealth Orbit**; **Nivesh** appears in legacy PRDs and issue dumps.

## Get started

- [getting-started.md](getting-started.md) — prerequisites, Supabase session pooler, `./scripts/setup.sh`, first login
- [setup.md](setup.md) — full guided setup, seeds, bulk sync, storage policy, troubleshooting

## Architecture

- [architecture.md](architecture.md) — FastAPI monolith, React `/ui/`, dual DB, in-process sync
- [superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md](superpowers/specs/2026-11-11-wealth-orbit-architecture-evaluation-design.md) — north-star evaluation (1.20+)

## Data

- [data/README.md](data/README.md) — index
- [data/overview.md](data/overview.md) — what lives where, retention tiers
- [data/portfolio.md](data/portfolio.md) — SQLite ledger, weighted average
- [data/market.md](data/market.md) — Postgres `market_data`, natural keys
- [data/mutual-fund-lineage.md](data/mutual-fund-lineage.md) — MF loaders (in-repo paths)
- [mutual-fund-data-lineage.md](mutual-fund-data-lineage.md) — redirect stub (superseded)

## API

- [api/overview.md](api/overview.md) — `/api/v1` route map
- Interactive OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (when API is running)

## Product / PRD

- [Nivesh_Product_Requirements_and_Roadmap_v1.1.md](Nivesh_Product_Requirements_and_Roadmap_v1.1.md) — current-scale PRD (large; use search)
- [Nivesh_Product_Requirements_and_Roadmap.md](Nivesh_Product_Requirements_and_Roadmap.md) — **archived** v1.0 baseline

## Releases

- [releases/README.md](releases/README.md) — frozen milestone catalog (1.2–1.27 outlines)

## Engineering glossary

- [glossary-engineering.md](glossary-engineering.md) — contributor terms (sync jobs, stances, pooler, tiers)

## Authoring (Varsity)

Local research copies and chapter index for glossary-style features (planned release **1.11** — not shipped in app code on this branch):

- [varsity_docs/chapter_index.json](varsity_docs/chapter_index.json)

PDFs under `varsity_docs/` are gitignored; download locally if needed for authoring.

## Archive

Stale snapshots — do not treat as current implementation truth:

- [archive/README.md](archive/README.md)
- Bannered: `nivesh_github_issues*.json`, Nov 2026 MVP plans under `superpowers/plans/2026-11-02-*`

## Component READMEs

| Path | Role |
|------|------|
| [../backend_api/README.md](../backend_api/README.md) | HTTP shell |
| [../portfolio-service/backend/README.md](../portfolio-service/backend/README.md) | Domain packages |
| [../frontend-react/README.md](../frontend-react/README.md) | Primary UI |
| [../frontend/README.md](../frontend/README.md) | Legacy Streamlit |
| [../screens/README.md](../screens/README.md) | Stock screen plugins |