"""Shared history depth presets for add / extend sync (5y | 10y | max)."""
from __future__ import annotations

from datetime import date, timedelta

HISTORY_PERIODS = ("5y", "10y", "max")
DEFAULT_HISTORY_PERIOD = "5y"

# Approximate lookbacks for providers that filter by calendar date (NAV).
_LOOKBACK_DAYS = {
    "5y": 365 * 5 + 2,
    "10y": 365 * 10 + 3,
}


def normalize_history_period(raw: str | None, *, default: str | None = DEFAULT_HISTORY_PERIOD) -> str | None:
    """Return a canonical period token, or None when unset and no default."""
    if raw is None or str(raw).strip() == "":
        return default
    value = str(raw).strip().lower()
    if value not in HISTORY_PERIODS:
        raise ValueError(f"invalid history_period: {raw}")
    return value


def history_period_from_date(period: str | None) -> date | None:
    """Earliest calendar date for date-filtered providers. None means unbounded (max)."""
    if period is None or period == "max":
        return None
    days = _LOOKBACK_DAYS.get(period)
    if days is None:
        raise ValueError(f"invalid history_period: {period}")
    return date.today() - timedelta(days=days)


def yfinance_period(period: str | None) -> str:
    """Yahoo ``period`` string for OHLC / index history downloads."""
    if period is None or period == "max":
        return "max"
    if period in HISTORY_PERIODS:
        return period
    raise ValueError(f"invalid history_period: {period}")
