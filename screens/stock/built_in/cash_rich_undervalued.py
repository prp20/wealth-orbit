"""Cash-rich undervalued screen."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "cash_rich_undervalued"
SCREEN_META = {
    "name": "Cash-rich undervalued",
    "version": "1.0.0",
    "description": "Lower PE with CFO covering most of net profit, low leverage, and a dividend floor.",
    "asset_class": "stock",
    "parameters": [
        {"name": "max_pe", "type": "float", "default": 20.0},
        {"name": "min_cfo_to_profit", "type": "float", "default": 0.8},
        {"name": "max_debt_to_equity", "type": "float", "default": 0.2},
        {"name": "min_roe", "type": "float", "default": 0.12},
        {"name": "min_market_cap_cr", "type": "float", "default": 200.0},
        {"name": "min_dividend_yield", "type": "float", "default": 1.0},
    ],
}


def screen(stocks, params):
    max_pe = param_float(params, "max_pe", 20.0)
    min_ratio = param_float(params, "min_cfo_to_profit", 0.8)
    max_de = param_float(params, "max_debt_to_equity", 0.2)
    min_roe = param_float(params, "min_roe", 0.12)
    min_mcap = param_float(params, "min_market_cap_cr", 200.0)
    min_dy = param_float(params, "min_dividend_yield", 1.0)
    cfo = col(stocks, "cfo")
    profit = col(stocks, "net_profit")
    mask = (
        col(stocks, "stock_pe").notna()
        & (col(stocks, "stock_pe") < max_pe)
        & cfo.notna()
        & profit.notna()
        & (cfo > profit * min_ratio)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "dividend_yield").notna()
        & (col(stocks, "dividend_yield") > min_dy)
    )
    return sort_by(stocks.loc[mask].copy(), "stock_pe", ascending=True)
