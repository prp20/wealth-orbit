"""Dividend aristocrats India."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "dividend_aristocrats_in"
SCREEN_META = {
    "name": "Dividend aristocrats India",
    "version": "1.0.0",
    "description": "Meaningful dividend yield with growth, ROE, and cash-flow support. Payout filter skipped when payout is missing.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_dividend_yield", "type": "float", "default": 2.0},
        {"name": "max_dividend_payout", "type": "float", "default": 0.50},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.10},
        {"name": "max_debt_to_equity", "type": "float", "default": 0.5},
        {"name": "min_roe", "type": "float", "default": 0.15},
        {"name": "min_market_cap_cr", "type": "float", "default": 1000.0},
    ],
}


def screen(stocks, params):
    min_dy = param_float(params, "min_dividend_yield", 2.0)
    max_payout = param_float(params, "max_dividend_payout", 0.50)
    min_pg = param_float(params, "min_profit_growth_3y", 0.10)
    max_de = param_float(params, "max_debt_to_equity", 0.5)
    min_roe = param_float(params, "min_roe", 0.15)
    min_mcap = param_float(params, "min_market_cap_cr", 1000.0)
    payout = col(stocks, "dividend_payout")
    payout_ok = payout.isna() | (payout < max_payout)
    mask = (
        col(stocks, "dividend_yield").notna()
        & (col(stocks, "dividend_yield") > min_dy)
        & payout_ok
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "cfo").notna()
        & (col(stocks, "cfo") > 0)
    )
    return sort_by(stocks.loc[mask].copy(), "dividend_yield", ascending=False)
