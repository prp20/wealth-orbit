# Equity data lineage

India-listed equities (NSE-first) in `market_data`.

## Masters

- Seed: `portfolio-service/scripts/seed/seed_stocks.py` from `data/seed/stocks.csv`.
- Natural key: `(exchange, trading_symbol)` with runtime Yahoo ticker `{symbol}.NS`.
- UI **Add stock** / `POST /api/v1/market-data/instruments/stocks` registers new masters then enqueues history.

## Price history (OHLC)

| Step | Component |
|------|-----------|
| Bulk | `portfolio-service/scripts/sync_yfinance.py` |
| Seed path | `seed_stock_prices.py`, flags on `run_seed_stocks.py` |
| Runtime | `market_data/sync.py` + stock sync POST `/api/v1/market-data/stocks/{symbol}/sync` |

Default period **10y**; explicit `max` only when you opt in.

## Fundamentals & shareholding

- Provider: `market_data/providers/screener.py`
- Scripts: `seed_fundamentals.py`, `--with-fundamentals` on `run_seed_stocks.py`
- Retention caps in `fundamentals_retention.py` (5 annual + 6 quarterly periods)

Slow and rate-limited — use small `--limit` first.

## Daily metrics & technicals

- `seed_stock_technicals.py` / `daily_metrics.py`
- Persists **latest** Yahoo ratios and **latest trading day** indicators only (not full indicator history)
- Requires OHLC present first

## Screener & peers

- List/filter/compare: `stock_screen.py`, `reference_service.py`
- Peers and valuation endpoints on `/api/v1/market-data/stocks/{symbol}/*`
- User screens: [../../screens/README.md](../../screens/README.md)

## FX (Home)

USD/INR optional via `EXCHANGE_RATE_API_KEY` in `market_data/fx_rates.py` — endpoint `GET /api/v1/market-data/fx/usd-inr`.