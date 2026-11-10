"""Capital-light B2B / services quality."""
from nivesh_screens import col, exclude_bfsi, param_bool, param_float, sort_by

SCREEN_ID = "capital_light_quality"
SCREEN_META = {
    "name": "Capital-light quality",
    "version": "1.0.0",
    "description": "High ROA/ROE and asset turnover with strong margins. Excludes BFSI by default.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_roa", "type": "float", "default": 0.15},
        {"name": "min_roe", "type": "float", "default": 0.20},
        {"name": "min_asset_turnover", "type": "float", "default": 1.0},
        {"name": "min_operating_margin", "type": "float", "default": 0.20},
        {"name": "max_debt_to_equity", "type": "float", "default": 0.3},
        {"name": "min_sales_growth_3y", "type": "float", "default": 0.15},
        {"name": "min_market_cap_cr", "type": "float", "default": 500.0},
        {"name": "exclude_bfsi", "type": "bool", "default": True},
    ],
}


def screen(stocks, params):
    min_roa = param_float(params, "min_roa", 0.15)
    min_roe = param_float(params, "min_roe", 0.20)
    min_at = param_float(params, "min_asset_turnover", 1.0)
    min_om = param_float(params, "min_operating_margin", 0.20)
    max_de = param_float(params, "max_debt_to_equity", 0.3)
    min_sg = param_float(params, "min_sales_growth_3y", 0.15)
    min_mcap = param_float(params, "min_market_cap_cr", 500.0)
    mask = (
        col(stocks, "roa").notna()
        & (col(stocks, "roa") > min_roa)
        & col(stocks, "roe").notna()
        & (col(stocks, "roe") > min_roe)
        & col(stocks, "asset_turnover").notna()
        & (col(stocks, "asset_turnover") > min_at)
        & col(stocks, "operating_margin").notna()
        & (col(stocks, "operating_margin") > min_om)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "sales_growth_3y").notna()
        & (col(stocks, "sales_growth_3y") > min_sg)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
    )
    if param_bool(params, "exclude_bfsi", True):
        mask &= exclude_bfsi(stocks)
    return sort_by(stocks.loc[mask].copy(), "roa", ascending=False)
