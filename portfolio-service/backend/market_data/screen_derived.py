"""Latest-only derived technical fields for the stock screen snapshot."""
from __future__ import annotations

import pandas as pd

DERIVED_FROM_OHLC_INPUTS = (
    "latest_volume",
    "vol_avg_20",
    "high_52w",
    "low_52w",
    "bb_upper",
    "bb_lower",
)

# Inputs that must be present (from SQL or stored technicals) before derived flags are trustworthy.
OHLC_OVERLAY_INPUT_COLUMNS: tuple[str, ...] = (
    "sma_50",
    "sma_200",
    "latest_volume",
    "vol_avg_20",
    "high_52w",
    "low_52w",
)


def overlay_input_null_mask(frame: pd.DataFrame) -> pd.Series:
    """True where any overlay input needed for derived technicals is missing."""
    if frame.empty:
        return pd.Series(dtype=bool)
    mask = pd.Series(False, index=frame.index)
    for column in OHLC_OVERLAY_INPUT_COLUMNS:
        if column not in frame.columns:
            return pd.Series(True, index=frame.index)
        mask |= pd.to_numeric(frame[column], errors="coerce").isna()
    return mask

DERIVED_SCREEN_COLUMNS: tuple[str, ...] = (
    "sma_50",
    "price_above_sma_50",
    "price_above_sma_200",
    "pct_from_sma_50",
    "pct_from_sma_200",
    "sma50_above_sma200",
    "rel_volume_20",
    "pct_from_52w_high",
    "pct_from_52w_low",
    "bb_percent_b",
)


def apply_derived_screen_fields(frame: pd.DataFrame) -> pd.DataFrame:
    """Add trader-oriented derived columns from latest OHLC / technical overlays."""
    if frame.empty:
        for column in DERIVED_SCREEN_COLUMNS:
            frame[column] = pd.Series(dtype="object")
        return frame

    out = frame.copy()

    def _series(name: str) -> pd.Series:
        if name in out.columns:
            return pd.to_numeric(out[name], errors="coerce")
        return pd.Series(pd.NA, index=out.index, dtype="Float64")

    price = _series("price_close")
    sma50 = _series("sma_50")
    sma200 = _series("sma_200")

    valid50 = price.notna() & sma50.notna() & (sma50 != 0)
    valid200 = price.notna() & sma200.notna() & (sma200 != 0)
    out["price_above_sma_50"] = (price > sma50).where(valid50)
    out["price_above_sma_200"] = (price > sma200).where(valid200)
    out["pct_from_sma_50"] = ((price / sma50) - 1.0).where(valid50)
    out["pct_from_sma_200"] = ((price / sma200) - 1.0).where(valid200)
    out["sma50_above_sma200"] = (sma50 > sma200).where(sma50.notna() & sma200.notna())

    vol = _series("latest_volume")
    vol_avg = _series("vol_avg_20")
    vol_ok = vol.notna() & vol_avg.notna() & (vol_avg != 0)
    out["rel_volume_20"] = (vol / vol_avg).where(vol_ok)

    high = _series("high_52w")
    low = _series("low_52w")
    high_ok = price.notna() & high.notna() & (high != 0)
    low_ok = price.notna() & low.notna() & (low != 0)
    out["pct_from_52w_high"] = ((price / high) - 1.0).where(high_ok)
    out["pct_from_52w_low"] = ((price / low) - 1.0).where(low_ok)

    upper = _series("bb_upper")
    lower = _series("bb_lower")
    span = upper - lower
    bb_ok = price.notna() & lower.notna() & span.notna() & (span != 0)
    out["bb_percent_b"] = ((price - lower) / span).where(bb_ok)

    return out