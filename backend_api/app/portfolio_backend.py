"""Single import boundary for the legacy ``portfolio-service`` package.

The service directory contains a hyphen, so it cannot be imported as a normal
Python package. Keep the compatibility path setup in exactly one module rather
than mutating ``sys.path`` independently in every router.
"""
from __future__ import annotations

import sys
from pathlib import Path

PORTFOLIO_SERVICE_ROOT = Path(__file__).resolve().parents[2] / "portfolio-service"

if str(PORTFOLIO_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_SERVICE_ROOT))

from backend.models import Holding, Portfolio, Transaction, TransactionType  # noqa: E402
from backend.mutual_fund_service import compute_metrics, has_nav_history, sync_nav  # noqa: E402
from backend.reference_service import (  # noqa: E402
    filter_values,
    mutual_fund_detail,
    mutual_fund_detail_by_name,
    mutual_fund_history,
    mutual_fund_similar,
    mutual_funds,
    stock_categories,
    stock_daily_metrics,
    stock_detail,
    stock_fundamentals,
    stock_history,
    stock_shareholding,
    stock_technical_indicators,
    stocks,
    sync_stock_fundamentals,
)
from backend.services import InsufficientHoldingsError  # noqa: E402

__all__ = [
    "Holding", "Portfolio", "Transaction", "TransactionType",
    "InsufficientHoldingsError", "compute_metrics", "filter_values",
    "has_nav_history", "mutual_fund_detail", "mutual_fund_detail_by_name",
    "mutual_fund_history", "mutual_fund_similar", "mutual_funds", "stock_categories",
    "stock_daily_metrics", "stock_detail", "stock_fundamentals", "stock_history",
    "stock_shareholding", "stock_technical_indicators", "stocks", "sync_nav",
    "sync_stock_fundamentals",
]
