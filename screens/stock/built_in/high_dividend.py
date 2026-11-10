"""Builtin high-dividend screen on stored daily metrics."""

SCREEN_ID = "high_dividend"
SCREEN_META = {
    "name": "High dividend",
    "version": "1.0.0",
    "description": "Stocks with dividend yield at or above a minimum.",
    "asset_class": "stock",
    "parameters": [
        {"name": "min_dividend_yield", "type": "float", "default": 2.0},
    ],
}


def screen(stocks, params):
    min_dy = float(params.get("min_dividend_yield", 2.0))
    out = stocks[
        stocks["dividend_yield"].notna() & (stocks["dividend_yield"] >= min_dy)
    ].copy()
    return out.sort_values("dividend_yield", ascending=False, na_position="last")
