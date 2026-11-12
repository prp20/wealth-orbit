"""Shared history depth presets for add / extend sync (5y | 10y | max)."""
from __future__ import annotations

from datetime import date, timedelta

HISTORY_PERIODS = ("5y", "10y", "max")
DEFAULT_HISTORY_PERIOD = "10y"
# Bulk seeders may also use shorter Yahoo periods; retention follows the same map.
BULK_YF_PERIODS = ("1y", "2y", "3y", "5y", "10y", "max")

# Approximate lookbacks for providers that filter by calendar date (NAV / prune).
_LOOKBACK_DAYS = {
    "1y": 365 + 1,
    "2y": 365 * 2 + 1,
    "3y": 365 * 3 + 2,
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


def retention_cutoff(period: str | None = DEFAULT_HISTORY_PERIOD) -> date | None:
    """Inclusive-earliest date to keep for a Yahoo/bulk period. None = keep all (max)."""
    if period is None or str(period).strip() == "":
        period = DEFAULT_HISTORY_PERIOD
    value = str(period).strip().lower()
    if value == "max":
        return None
    if value not in _LOOKBACK_DAYS:
        raise ValueError(f"invalid retention period: {period}")
    return date.today() - timedelta(days=_LOOKBACK_DAYS[value])


def yfinance_period(period: str | None) -> str:
    """Yahoo ``period`` string for OHLC / index history downloads."""
    if period is None or period == "":
        return DEFAULT_HISTORY_PERIOD
    value = str(period).strip().lower()
    if value == "max":
        return "max"
    if value in BULK_YF_PERIODS:
        return value
    if value in HISTORY_PERIODS:
        return value
    raise ValueError(f"invalid history_period: {period}")
