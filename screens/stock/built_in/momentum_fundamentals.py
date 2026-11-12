"""Momentum + fundamentals (Canslim-style)."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "momentum_fundamentals"
SCREEN_META = {
    "name": "Momentum + fundamentals",
    "version": "1.0.0",
    "description": "Growth and ROE with price above SMA200. Rows without SMA200 are excluded honestly.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.20},
        {"name": "min_sales_growth_3y", "type": "float", "default": 0.15},
        {"name": "min_roe", "type": "float", "default": 0.15},
        {"name": "min_promoter_holding", "type": "float", "default": 0.40},
        {"name": "min_market_cap_cr", "type": "float", "default": 1000.0},
        {"name": "max_pledged_pct", "type": "float", "default": 0.10},
    ],
}


def screen(stocks, params):
    min_pg = param_float(params, "min_profit_growth_3y", 0.20)
    min_sg = param_float(params, "min_sales_growth_3y", 0.15)
    min_roe = param_float(params, "min_roe", 0.15)
    min_prom = param_float(params, "min_promoter_holding", 0.40)
    min_mcap = param_float(params, "min_market_cap_cr", 1000.0)
    max_pledge = param_float(params, "max_pledged_pct", 0.10)
    price = col(stocks, "price_close")
    sma = col(stocks, "sma_200")
    pledge = col(stocks, "pledged_pct")
    pledge_ok = pledge.isna() | (pledge < max_pledge)
    mask = (
        col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "sales_growth_3y").notna()
        & (col(stocks, "sales_growth_3y") > min_sg)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "promoter_holding").notna()
        & (col(stocks, "promoter_holding") > min_prom)
        & price.notna()
        & sma.notna()
        & (price > sma)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & pledge_ok
    )
    return sort_by(stocks.loc[mask].copy(), "profit_growth_3y", ascending=False)
