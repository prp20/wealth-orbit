"""Small-cap hidden gems."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "small_cap_hidden_gems"
SCREEN_META = {
    "name": "Small cap hidden gems",
    "version": "1.0.0",
    "description": "Smaller market-cap names with high ROE, low leverage, and strong growth. Pledge filter skipped when data is missing.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_market_cap_cr", "type": "float", "default": 100.0},
        {"name": "max_market_cap_cr", "type": "float", "default": 5000.0},
        {"name": "min_roe", "type": "float", "default": 0.18},
        {"name": "max_debt_to_equity", "type": "float", "default": 0.3},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.25},
        {"name": "min_promoter_holding", "type": "float", "default": 0.50},
        {"name": "max_pledged_pct", "type": "float", "default": 0.05},
        {"name": "min_interest_coverage", "type": "float", "default": 5.0},
    ],
}


def screen(stocks, params):
    min_mcap = param_float(params, "min_market_cap_cr", 100.0)
    max_mcap = param_float(params, "max_market_cap_cr", 5000.0)
    min_roe = param_float(params, "min_roe", 0.18)
    max_de = param_float(params, "max_debt_to_equity", 0.3)
    min_pg = param_float(params, "min_profit_growth_3y", 0.25)
    min_prom = param_float(params, "min_promoter_holding", 0.50)
    max_pledge = param_float(params, "max_pledged_pct", 0.05)
    min_ic = param_float(params, "min_interest_coverage", 5.0)
    pledge = col(stocks, "pledged_pct")
    pledge_ok = pledge.isna() | (pledge < max_pledge)
    mask = (
        col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & (col(stocks, "market_cap_cr") < max_mcap)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "promoter_holding").notna()
        & (col(stocks, "promoter_holding") > min_prom)
        & col(stocks, "interest_coverage").notna()
        & (col(stocks, "interest_coverage") > min_ic)
        & pledge_ok
    )
    return sort_by(stocks.loc[mask].copy(), "roe", ascending=False)
