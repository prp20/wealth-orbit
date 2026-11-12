# Stock screen plugins

Drop a Python file under `screens/stock/user/` (or ship one under `built_in/`), refresh discovery, and the platform lists it if validation passes.

## File contract

```python
from nivesh_screens import col, param_float, sort_by

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
    """Filter/sort the allowlisted snapshot DataFrame (or return trading_symbol list)."""
    out = stocks[
        stocks["stock_pe"].notna()
        & (stocks["stock_pe"] <= params["max_pe"])
        & stocks["roe"].notna()
        & (stocks["roe"] >= params["min_roe"])
    ]
    return out.sort_values("market_cap", ascending=False)
```

Optional helper import: `nivesh_screens` (BFSI exclude, param coercion, null-safe columns).

## Units (locked)

| Field family | Snapshot unit | Screener.in-style paste |
|--------------|---------------|-------------------------|
| ROE, ROCE, ROA, margins, growth, payout, pledge, promoter | **Fractions** (0.15 = 15%) | `> 15` → plugin uses `> 0.15` |
| Dividend yield | **Percent points** (2.0 = 2%) | `> 2` → `> 2` |
| Market cap thresholds | Prefer **`market_cap_cr`** (₹ Cr) | `> 500` → `market_cap_cr > 500` |
| Earnings yield | Fraction (`1/stock_pe`) | `> 5%` → `> 0.05` |
| P/E, D/E, coverage, turnover | Same numeric sense as store | as written |

Sparse fundamentals mean required `.notna()` filters shrink results until sync fills them. Missing optional fields (pledge, current ratio, payout) skip that predicate when null.

## Allowlisted columns

Identity: `trading_symbol`, `company_name`, `exchange`, `sector_name`, `industry_name`, `market_cap_class`

Prices / technicals: `price_close`, `sma_200`

Daily metrics: `market_cap`, `market_cap_cr`, `stock_pe`, `price_to_book`, `dividend_yield`, `book_value`, `roce`, `roe`, `enterprise_value`, `ebitda_ttm`, `ev_ebitda`, `ev_sales`, `net_debt`, `fcf_yield`, `peg`, `earnings_yield`, `metrics_date`

Fundamentals / derived: `debt_to_equity`, `interest_coverage`, `operating_margin`, `roa`, `asset_turnover`, `profit_growth_3y`, `sales_growth_3y`, `cfo`, `net_profit`

Shareholding: `promoter_holding`, `pledged_pct` (often null)

Often null until stored: `current_ratio`, `dividend_payout`

## Built-in playbook screens

| Id | Name |
|----|------|
| `consistent_compounders` | Consistent compounders |
| `garp` | GARP |
| `debt_free_high_growth` | Debt-free high growth |
| `magic_formula_in` | Magic Formula India |
| `small_cap_hidden_gems` | Small cap hidden gems |
| `cash_rich_undervalued` | Cash-rich undervalued |
| `momentum_fundamentals` | Momentum + fundamentals |
| `dividend_aristocrats_in` | Dividend aristocrats India |
| `turnaround_candidates` | Turnaround candidates |
| `capital_light_quality` | Capital-light quality |

Thin samples also kept: `quality_value`, `high_dividend`.

## Operator steps

1. Copy a sample from `screens/stock/built_in/`
2. Edit metadata + `screen()`
3. Place under `screens/stock/user/`
4. **Stocks → Screener → Refresh screens** (or `POST /api/v1/market-data/stocks/screens/refresh`)
5. Run → open a result into stock detail

Disable without deleting: add the `SCREEN_ID` to `disabled_ids` in `screens/registry.yaml`.
