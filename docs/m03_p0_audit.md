# M03 P0 audit (EQ-01 / 02 / 04 / 07 / 11)

Audited against `main` + this M03 P0 branch. Symbol used for smoke intent: RELIANCE (NSE).

| Story | Status | Notes |
|-------|--------|-------|
| EQ-01 Company master (#19) | Partial → improved | Enriched detail now exposes `isin`, `bse_code`, `listing_date`, `listing_status`, `market_cap_class`. `stock_identity_events` table exists; **no ingest yet**. Seed CSV still NSE-centric. |
| EQ-02 Daily OHLCV (#20) | Partial | Yahoo OHLCV + freshness OK. `adj_close` + `corporate_actions` stubbed; **CA-adjusted history unavailable** until licensed feed. Delivery volume not licensed. |
| EQ-04 Core fundamentals (#22) | Done (MVP) | Summary groups for profitability / growth / leverage / cash-flow with definitions; SA≠consol enforced by filters. Extended ratios remain P1. |
| EQ-07 Technicals (#25) | Done (MVP) | SMA/EMA, RSI, MACD, Bollinger, **ATR** via sync. No pattern engine / Fib / Heikin Ashi (P1). |
| EQ-11 Detail page (#29) | Done (core) | `?tab=` Overview \| Statements \| Fundamentals \| Valuation \| Technicals. Peers + shareholding on Overview. Insights placeholder empty. |

## Data sources (research/MVP)

- Prices / daily metrics: **yfinance** (unofficial; not for redistribution)
- Statements / shareholding: **Screener.in** scrape (on-demand; ToS/rate-limit risk)
- Technicals: **derived** from stored OHLCV
- Master: **CSV seed**

## Intentionally open / deferred

- EQ-06 DCF (#24), EQ-08 extras (#26), EQ-09 governance (#27), EQ-10 deep peers (#28)
- W3 pipeline coverage (#66)
- Identity-event backfill and CA ingest
