"""Tiny helpers for stock screen plugins (allowlisted import)."""
from __future__ import annotations

from typing import Any

import pandas as pd

BFSI_SECTOR_NEEDLES = (
    "bank",
    "banking",
    "finance",
    "financial",
    "insurance",
    "nbfc",
)

BFSI_INDUSTRY_NEEDLES = (
    "bank",
    "banking",
    "finance",
    "financial",
    "insurance",
    "nbfc",
    "housing finance",
)


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return number


def param_float(params: dict, name: str, default: float) -> float:
    value = as_float(params.get(name), default)
    return default if value is None else value


def param_bool(params: dict, name: str, default: bool = True) -> bool:
    raw = params.get(name, default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    text = str(raw).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def exclude_bfsi(frame: pd.DataFrame) -> pd.Series:
    """True for rows that are NOT BFSI (keep industrial screens honest)."""
    sector = frame.get("sector_name")
    industry = frame.get("industry_name")
    sector_text = sector.fillna("").astype(str).str.lower() if sector is not None else ""
    industry_text = industry.fillna("").astype(str).str.lower() if industry is not None else ""
    mask = pd.Series(True, index=frame.index)
    for needle in BFSI_SECTOR_NEEDLES:
        mask &= ~sector_text.str.contains(needle, regex=False)
    for needle in BFSI_INDUSTRY_NEEDLES:
        mask &= ~industry_text.str.contains(needle, regex=False)
    return mask


def col(frame: pd.DataFrame, name: str) -> pd.Series:
    if name in frame.columns:
        return frame[name]
    return pd.Series([None] * len(frame), index=frame.index)


def sort_by(frame: pd.DataFrame, column: str, *, ascending: bool = False) -> pd.DataFrame:
    if column not in frame.columns or frame.empty:
        return frame
    return frame.sort_values(column, ascending=ascending, na_position="last")
