"""Consistent compounders — quality compounders on stored fundamentals."""
from nivesh_screens import col, exclude_bfsi, param_bool, param_float, sort_by

SCREEN_ID = "consistent_compounders"
SCREEN_META = {
    "name": "Consistent compounders",
    "version": "1.0.0",
    "description": "High ROCE and growth with low leverage and solid promoter holding. Excludes BFSI by default.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_roce", "type": "float", "default": 0.20},
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.15},
        {"name": "min_sales_growth_3y", "type": "float", "default": 0.15},
        {"name": "max_debt_to_equity", "type": "float", "default": 0.5},
        {"name": "min_market_cap_cr", "type": "float", "default": 500.0},
        {"name": "min_promoter_holding", "type": "float", "default": 0.40},
        {"name": "min_operating_margin", "type": "float", "default": 0.15},
        {"name": "exclude_bfsi", "type": "bool", "default": True},
    ],
}


def screen(stocks, params):
    min_roce = param_float(params, "min_roce", 0.20)
    min_pg = param_float(params, "min_profit_growth_3y", 0.15)
    min_sg = param_float(params, "min_sales_growth_3y", 0.15)
    max_de = param_float(params, "max_debt_to_equity", 0.5)
    min_mcap = param_float(params, "min_market_cap_cr", 500.0)
    min_prom = param_float(params, "min_promoter_holding", 0.40)
    min_om = param_float(params, "min_operating_margin", 0.15)
    mask = (
        col(stocks, "roce").notna()
        & (col(stocks, "roce") > min_roce)
        & col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "sales_growth_3y").notna()
        & (col(stocks, "sales_growth_3y") > min_sg)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "promoter_holding").notna()
        & (col(stocks, "promoter_holding") > min_prom)
        & col(stocks, "operating_margin").notna()
        & (col(stocks, "operating_margin") > min_om)
    )
    if param_bool(params, "exclude_bfsi", True):
        mask &= exclude_bfsi(stocks)
    return sort_by(stocks.loc[mask].copy(), "roce", ascending=False)
