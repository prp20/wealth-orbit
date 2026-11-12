"""Magic Formula (India) — high ROCE and earnings yield."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "magic_formula_in"
SCREEN_META = {
    "name": "Magic Formula India",
    "version": "1.0.0",
    "description": "High ROCE with earnings yield floor (1/PE). Sort by ROCE; cross-check earnings yield on detail.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_roce", "type": "float", "default": 0.25},
        {"name": "min_earnings_yield", "type": "float", "default": 0.05},
        {"name": "min_market_cap_cr", "type": "float", "default": 500.0},
        {"name": "max_debt_to_equity", "type": "float", "default": 1.0},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.10},
    ],
}


def screen(stocks, params):
    min_roce = param_float(params, "min_roce", 0.25)
    min_ey = param_float(params, "min_earnings_yield", 0.05)
    min_mcap = param_float(params, "min_market_cap_cr", 500.0)
    max_de = param_float(params, "max_debt_to_equity", 1.0)
    min_pg = param_float(params, "min_profit_growth_3y", 0.10)
    pe = col(stocks, "stock_pe")
    mask = (
        col(stocks, "roce").notna()
        & (col(stocks, "roce") > min_roce)
        & col(stocks, "earnings_yield").notna()
        & (col(stocks, "earnings_yield") > min_ey)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & pe.notna()
        & (pe > 0)
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
    )
    return sort_by(stocks.loc[mask].copy(), "roce", ascending=False)
