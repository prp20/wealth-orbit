# Wealth Orbit — pending todos

Tracked follow-ups from PR #2 code review (Standards + Spec) and the post-B1 roadmap. Check items off as they land.

## From PR review (Standards)

- [ ] Extract a shared “latest price + daily metrics” helper in [`portfolio-service/backend/reference_service.py`](../portfolio-service/backend/reference_service.py); batch peers queries instead of N+1 per symbol
- [ ] Single source of truth for stock sync kind names in [`backend_api/app/market_data_routes.py`](../backend_api/app/market_data_routes.py) (route validation vs `STOCK_SYNC_KINDS`)
- [ ] Reuse [`frontend-react/src/lib/format.ts`](../frontend-react/src/lib/format.ts) from portfolio pages in [`frontend-react/src/app/App.tsx`](../frontend-react/src/app/App.tsx) instead of the local `money` helper
- [ ] Unify page chrome on `PageHeader` for funds/portfolio (or document stocks-only deliberately)
- [ ] Replace [`ChartToolbar`](../frontend-react/src/components/ChartToolbar.tsx) nested ternaries with a `Record<ChartRange, number>` months map

## From PR review (Spec)

- [ ] Add technical indicator spark / last-points series in [`TechnicalsPanel.tsx`](../frontend-react/src/pages/stocks/panels/TechnicalsPanel.tsx)
- [ ] Align FE sync failure UX with job status: remove or gate the zero-row SUCCEEDED→failed heuristic in `syncJobFailureMessage` ([`frontend-react/src/api.ts`](../frontend-react/src/api.ts))
- [ ] Optional: dedicated Sync kinds cluster on the stock detail page if product prefers the original B1 layout over per-panel sync

## Roadmap (post-B1)

- [x] **B2** — Mutual fund parity (same list/detail/chart/sync/insights bar as stocks)
- [ ] **A** — Portfolio usefulness (React TX create/import, mark-to-market, PnL / XIRR)
- [ ] **C** — Platform foundations (light auth, durable sync workers, retire Streamlit when React covers portfolio)
- [ ] **D** — Agentic Insights fill (populate Insights slot with structured suggestions)
