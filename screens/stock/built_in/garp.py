"""GARP — growth at a reasonable price."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "garp"
SCREEN_META = {
    "name": "GARP",
    "version": "1.0.0",
    "description": "Growth at a reasonable price: PE under a cap with ROE and 3y growth floors. Mentally check growth vs PE on the detail page.",
    "asset_class": "stock",
    "parameters": [
        {"name": "max_pe", "type": "float", "default": 30.0},
        {"name": "min_roe", "type": "float", "default": 0.18},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.20},
        {"name": "max_debt_to_equity", "type": "float", "default": 1.0},
        {"name": "min_sales_growth_3y", "type": "float", "default": 0.15},
        {"name": "min_market_cap_cr", "type": "float", "default": 1000.0},
    ],
}


def screen(stocks, params):
    max_pe = param_float(params, "max_pe", 30.0)
    min_roe = param_float(params, "min_roe", 0.18)
    min_pg = param_float(params, "min_profit_growth_3y", 0.20)
    max_de = param_float(params, "max_debt_to_equity", 1.0)
    min_sg = param_float(params, "min_sales_growth_3y", 0.15)
    min_mcap = param_float(params, "min_market_cap_cr", 1000.0)
    pe = col(stocks, "stock_pe")
    mask = (
        pe.notna()
        & (pe > 0)
        & (pe < max_pe)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "sales_growth_3y").notna()
        & (col(stocks, "sales_growth_3y") > min_sg)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
    )
    return sort_by(stocks.loc[mask].copy(), "stock_pe", ascending=True)
