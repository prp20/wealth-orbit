# Stock screen plugins

Drop a Python file under `screens/stock/user/` (or ship one under `built_in/`), refresh discovery, and the platform lists it if validation passes.

## File contract

```python
SCREEN_ID = "my_quality_value"
SCREEN_META = {
    "name": "My quality value",
    "version": "1.0.0",
    "description": "PE and ROE bands on stored metrics",
    "asset_class": "stock",
    "parameters": [
        {"name": "max_pe", "type": "float", "default": 25.0},
        {"name": "min_roe", "type": "float", "default": 0.15},
    ],
}

def screen(stocks, params):
    """Filter/sort the allowlisted snapshot DataFrame (or return trading_symbol list).

    ROE/ROCE are stored as fractions (0.15 = 15%). Dividend yield is percent points.
    """
    out = stocks[
        stocks["stock_pe"].notna()
        & (stocks["stock_pe"] <= params["max_pe"])
        & stocks["roe"].notna()
        & (stocks["roe"] >= params["min_roe"])
    ]
    return out.sort_values("market_cap", ascending=False)
```

## Rules

- Only `.py` files under roots listed in `screens/registry.yaml`
- Required: `SCREEN_ID`, `SCREEN_META`, `screen(stocks, params)`
- `asset_class` must be `"stock"` for stock roots
- Imports are allowlisted (stdlib math helpers + pandas provided by the runner)
- Forbidden: `os`, `subprocess`, `socket`, DB drivers, network clients, arbitrary file I/O
- Screens read **stored** snapshot columns only — no live scrape

## Allowlisted columns

`trading_symbol`, `company_name`, `exchange`, `sector_name`, `industry_name`,
`market_cap_class`, `price_close`, `market_cap`, `stock_pe`, `price_to_book`,
`dividend_yield`, `book_value`, `roce`, `roe`, `enterprise_value`, `ebitda_ttm`,
`ev_ebitda`, `ev_sales`, `net_debt`, `fcf_yield`, `peg`, `metrics_date`

## Operator steps

1. Copy a sample from `screens/stock/built_in/`
2. Edit metadata + `screen()`
3. Place under `screens/stock/user/`
4. In the UI, open **Stocks → Screener → Refresh screens**, or call `POST /api/v1/market-data/stocks/screens/refresh`
5. Run the screen; open a result row into stock detail

Disable without deleting: add the `SCREEN_ID` to `disabled_ids` in `screens/registry.yaml`.
