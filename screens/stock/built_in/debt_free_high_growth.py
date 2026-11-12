"""Debt-free high-growth screen."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "debt_free_high_growth"
SCREEN_META = {
    "name": "Debt-free high growth",
    "version": "1.0.0",
    "description": "Near debt-free balance sheets with strong 3y growth and positive operating cash flow.",
    "asset_class": "stock",
    "parameters": [
        {"name": "max_debt_to_equity", "type": "float", "default": 0.1},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.20},
        {"name": "min_sales_growth_3y", "type": "float", "default": 0.15},
        {"name": "min_roe", "type": "float", "default": 0.15},
        {"name": "min_market_cap_cr", "type": "float", "default": 200.0},
        {"name": "min_current_ratio", "type": "float", "default": 1.5},
    ],
}


def screen(stocks, params):
    max_de = param_float(params, "max_debt_to_equity", 0.1)
    min_pg = param_float(params, "min_profit_growth_3y", 0.20)
    min_sg = param_float(params, "min_sales_growth_3y", 0.15)
    min_roe = param_float(params, "min_roe", 0.15)
    min_mcap = param_float(params, "min_market_cap_cr", 200.0)
    min_cr = param_float(params, "min_current_ratio", 1.5)
    cr = col(stocks, "current_ratio")
    # current_ratio is often null in the snapshot — skip that predicate when absent.
    cr_ok = cr.isna() | (cr > min_cr)
    mask = (
        col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "sales_growth_3y").notna()
        & (col(stocks, "sales_growth_3y") > min_sg)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "cfo").notna()
        & (col(stocks, "cfo") > 0)
        & cr_ok
    )
    return sort_by(stocks.loc[mask].copy(), "profit_growth_3y", ascending=False)
