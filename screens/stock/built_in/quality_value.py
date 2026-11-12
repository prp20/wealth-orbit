"""Builtin quality/value screen on stored daily metrics."""

SCREEN_ID = "quality_value"
SCREEN_META = {
    "name": "Quality value",
    "version": "1.0.0",
    "description": "Stocks with PE at or below a max and ROE at or above a min (ROE is a fraction: 0.15 = 15%).",
    "asset_class": "stock",
    "parameters": [
        {"name": "max_pe", "type": "float", "default": 25.0},
        {"name": "min_roe", "type": "float", "default": 0.15},
    ],
}


def screen(stocks, params):
    max_pe = float(params.get("max_pe", 25.0))
    min_roe = float(params.get("min_roe", 0.15))
    out = stocks[
        stocks["stock_pe"].notna()
        & (stocks["stock_pe"] <= max_pe)
        & stocks["roe"].notna()
        & (stocks["roe"] >= min_roe)
    ].copy()
    return out.sort_values("market_cap", ascending=False, na_position="last")
