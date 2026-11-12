"""Turnaround candidates — high risk / high change."""
from nivesh_screens import col, param_float, sort_by

SCREEN_ID = "turnaround_candidates"
SCREEN_META = {
    "name": "Turnaround candidates",
    "version": "1.0.0",
    "description": "High 3y profit growth with improving quality filters. High risk — verify the story on the detail page.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_profit_growth_3y", "type": "float", "default": 0.30},
        {"name": "min_roce", "type": "float", "default": 0.12},
        {"name": "max_debt_to_equity", "type": "float", "default": 1.5},
        {"name": "min_interest_coverage", "type": "float", "default": 2.0},
        {"name": "min_market_cap_cr", "type": "float", "default": 200.0},
        {"name": "min_promoter_holding", "type": "float", "default": 0.45},
        {"name": "min_operating_margin", "type": "float", "default": 0.08},
    ],
}


def screen(stocks, params):
    min_pg = param_float(params, "min_profit_growth_3y", 0.30)
    min_roce = param_float(params, "min_roce", 0.12)
    max_de = param_float(params, "max_debt_to_equity", 1.5)
    min_ic = param_float(params, "min_interest_coverage", 2.0)
    min_mcap = param_float(params, "min_market_cap_cr", 200.0)
    min_prom = param_float(params, "min_promoter_holding", 0.45)
    min_om = param_float(params, "min_operating_margin", 0.08)
    mask = (
        col(stocks, "profit_growth_3y").notna()
        & (col(stocks, "profit_growth_3y") > min_pg)
        & col(stocks, "roce").notna()
        & (col(stocks, "roce") > min_roce)
        & col(stocks, "debt_to_equity").notna()
        & (col(stocks, "debt_to_equity") < max_de)
        & col(stocks, "interest_coverage").notna()
        & (col(stocks, "interest_coverage") > min_ic)
        & col(stocks, "market_cap_cr").notna()
        & (col(stocks, "market_cap_cr") > min_mcap)
        & col(stocks, "promoter_holding").notna()
        & (col(stocks, "promoter_holding") > min_prom)
        & col(stocks, "operating_margin").notna()
        & (col(stocks, "operating_margin") > min_om)
    )
    return sort_by(stocks.loc[mask].copy(), "profit_growth_3y", ascending=False)
