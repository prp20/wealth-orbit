# Wealth Orbit documentation

Handbook for contributors and operators. Product name in the UI is **Wealth Orbit**; **Nivesh** appears in legacy PRDs and issue dumps.

## Get started

- [getting-started.md](getting-started.md) — prerequisites, Supabase session pooler, `./scripts/setup.sh`, first login
- [setup.md](setup.md) — full guided setup, seeds, bulk sync, storage policy, troubleshooting

## Architecture

- [architecture.md](architecture.md) — FastAPI monolith, React `/ui/`, dual DB, in-process sync

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

## Engineering glossary

- [glossary-engineering.md](glossary-engineering.md) — contributor terms (sync jobs, stances, pooler, tiers)

## Authoring (Varsity)

Local research copies and chapter index for the **1.11** glossary chat (seed + Varsity links):

- [varsity_docs/chapter_index.json](varsity_docs/chapter_index.json)
- [varsity_docs/glossary_seed.json](varsity_docs/glossary_seed.json)

PDFs under `varsity_docs/` are gitignored (local authoring / future RAG ingest only).

## Local-only (gitignored)

These folders stay on your machine for planning; they are **not** in the remote repo:

- `docs/releases/` — milestone outlines
- `docs/superpowers/` — agent plans and architecture evaluation specs

## Archive

Stale snapshots — do not treat as current implementation truth:

- [archive/README.md](archive/README.md)
- Bannered: `nivesh_github_issues*.json` (see [nivesh_github_issues.ARCHIVE-NOTICE.md](nivesh_github_issues.ARCHIVE-NOTICE.md))

## Component READMEs

| Path | Role |
|------|------|
| [../backend_api/README.md](../backend_api/README.md) | HTTP shell |
| [../portfolio-service/backend/README.md](../portfolio-service/backend/README.md) | Domain packages |
| [../frontend-react/README.md](../frontend-react/README.md) | Primary UI |
| [../frontend/README.md](../frontend/README.md) | Legacy Streamlit |
| [../screens/README.md](../screens/README.md) | Stock screen plugins |