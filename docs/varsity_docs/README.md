# Zerodha Varsity local corpus

Offline research copies and structured indexes for Nivesh glossary authoring (**release 1.11**).

## Copyright & credit

Wealth Orbit is a **learning project**. If you use Zerodha Varsity documents (or extracts derived from them) while exploring this repo:

- **All credit for Varsity educational content belongs to Zerodha.** Varsity materials are © Zerodha.
- Reproduction or redistribution of Varsity PDFs, full chapter text, or images is **not** permitted by Varsity and is **not** authorized by this project.
- PDFs and RAG extracts under this folder are **local research copies only** (gitignored). Do **not** ship or publish them with the app.
- The in-app glossary uses **our** short curated definitions plus citations (module/chapter title + URL) via `glossary_seed.json` — not wholesale Varsity text.

## Files

| File | Role |
|------|------|
| `*.pdf` | Official module PDFs where available (gitignored) |
| `chapter_index.json` | All 17 modules: titles, URLs, chapter lists (blurbs are public teasers) |
| `glossary_seed.json` | Curated terms with original definitions + Varsity citations |

## Naming

Prefer `Module_<N>_<slug>.pdf` for new downloads. Older files may use spaces (`Module N_...pdf`); both are valid local paths recorded in `chapter_index.json` → `pdf_local`.

## Inventory

| # | Module | Listed ch. | Indexed | Local PDF | URL |
|---|--------|------------|---------|-----------|-----|
| 1 | Introduction to Stock Markets | 15 | 15 | `Module 1_Introduction to Stock Markets.pdf` | https://zerodha.com/varsity/module/introduction-to-stock-markets/ |
| 2 | Technical Analysis | 22 | 22 | `Module 2_Technical Analysis.pdf` | https://zerodha.com/varsity/module/technical-analysis/ |
| 3 | Fundamental Analysis | 16 | 16 | `Module 3_Fundamental Analysis.pdf` | https://zerodha.com/varsity/module/fundamental-analysis/ |
| 4 | Futures Trading | 13 | 13 | `Module_4_Futures_Trading.pdf` | https://zerodha.com/varsity/module/futures-trading/ |
| 5 | Options Theory for Professional Trading | 25 | 23 | `Module_5_Options_Theory.pdf` | https://zerodha.com/varsity/module/option-theory/ |
| 6 | Option Strategies | 14 | 14 | `Module_6_Option_Strategies.pdf` | https://zerodha.com/varsity/module/option-strategies/ |
| 7 | Markets and Taxation | 8 | 8 | `Module 7_Markets & Taxation.pdf` | https://zerodha.com/varsity/module/markets-and-taxation/ |
| 8 | Currency, Commodity, and Government Securities | 20 | 20 | `Module 8_Currency and Commodity Futures.pdf` | https://zerodha.com/varsity/module/commodities-currency-government-securities/ |
| 9 | Risk Management and Trading Psychology | 16 | 12 | `Module 9_Risk Management & Trading Psychology.pdf` | https://zerodha.com/varsity/module/risk-management/ |
| 10 | Trading Systems | 16 | 16 | `Module 10_Trading Systems.pdf` | https://zerodha.com/varsity/module/trading-systems/ |
| 11 | Personal Finance - Mutual Funds | 33 | 32 | `Module11_Personal-Finance.pdf` | https://zerodha.com/varsity/module/personalfinance/ |
| 12 | Innerworth - Mind over markets | 603 | 603 | `— (none)` | https://zerodha.com/varsity/module/innerworth/ |
| 13 | Integrated Financial Modelling | 18 | 18 | `Module_13_Integrated_Financial_Modelling.pdf` | https://zerodha.com/varsity/module/financial-modelling/ |
| 14 | Personal Finance - Insurance | 9 | 9 | `Module 14_Personal Finance Insurance.pdf` | https://zerodha.com/varsity/module/insurance/ |
| 15 | Sector Analysis | 17 | 17 | `— (none)` | https://zerodha.com/varsity/module/sector-analysis/ |
| 16 | Social Stock Exchanges (SSEs) | 4 | 4 | `— (none)` | https://zerodha.com/varsity/module/social-stock-exchanges-sses/ |
| 17 | NPS: National Pension System | 9 | 9 | `— (none)` | https://zerodha.com/varsity/module/national-pension-scheme/ |

### PDF gaps

- **12 Innerworth:** no Download PDF on the module page — chapter index only (603 titles/URLs).
- **15 Sector Analysis, 16 SSEs, 17 NPS:** no Download PDF link on the module page at scrape time — chapter index only.
- **13 Financial Modelling:** Download PDF points at Google Drive; local PDF saved when download succeeded.

Source catalog: https://zerodha.com/varsity/modules/

## Glossary chat (release 1.11)

The in-app glossary is **definitions only**: short answers from `glossary_seed.json` plus Varsity chapter links. It does **not** give buy, sell, switch, or personalized advice, and it does not invent live prices or portfolio numbers.

- **Varsity PDFs** in this folder stay **offline research copies** (gitignored). They are not served by the app.
- **Public API** (no login): `POST /api/v1/glossary/chat` (single message) and `POST /api/v1/glossary/agent/chat` (multi-turn agent with seed fallback when `GROQ_API_KEY` is unset). Browse: `GET /api/v1/glossary/terms`.
- **UI:** React route `/glossary` (Glossary in the nav).
- **Env:** `GROQ_API_KEY` and optional `GLOSSARY_LLM_MODEL` — see [setup.md](../setup.md#glossary-chat-release-111).

Exit smoke (pytest): IPO match, advice/dump refusal, and agent guards — `tests/test_glossary_api.py`, `tests/test_glossary_agent.py`, `tests/test_glossary_seed_matcher.py`.

