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

from backend.models import Holding, Portfolio, Transaction, TransactionType, User  # noqa: E402
from backend.mutual_fund_service import compute_metrics, has_nav_history, sync_nav  # noqa: E402
from backend.market_data.mutual_fund_analytics import METRIC_PERIODS  # noqa: E402
from backend.market_data.mutual_fund_holdings import sync_holdings, sync_managers  # noqa: E402
from backend.market_data.mutual_fund_sync import recompute_metrics, sync_benchmark, sync_enrichment  # noqa: E402
from backend.market_data.index_sync import sync_home_indexes  # noqa: E402
from backend.market_data.stock_screen import (  # noqa: E402
    STOCK_SCREEN_SORT_COLUMNS,
    stock_screen,
)
from backend.screen_plugins import (  # noqa: E402
    list_screens,
    refresh_screens,
    run_screen,
)
from backend.reference_service import (  # noqa: E402
    SCREEN_SORT_COLUMNS,
    filter_values,
    mutual_fund_detail,
    mutual_fund_detail_by_name,
    match_mutual_fund_codes,
    mutual_fund_detail_enriched,
    mutual_fund_history,
    mutual_fund_metric_snapshots,
    mutual_fund_enrichment,
    mutual_fund_benchmark,
    mutual_fund_benchmark_history,
    benchmark_list,
    benchmark_history,
    benchmark_snapshot,
    mutual_fund_similar,
    mutual_fund_similar_enriched,
    mutual_fund_screen,
    mutual_fund_compare,
    mutual_fund_holdings_snapshot,
    mutual_fund_overlap,
    mutual_fund_managers,
    mutual_funds,
    stock_categories,
    stock_compare,
    stock_daily_metrics,
    stock_detail,
    stock_detail_enriched,
    stock_fundamentals,
    stock_fundamentals_summary,
    stock_history,
    stock_peers,
    stock_shareholding,
    stock_technical_indicators,
    stock_valuation,
    stocks,
    sync_stock_fundamentals,
)
from backend.services import InsufficientHoldingsError  # noqa: E402

__all__ = [
    "Holding", "Portfolio", "Transaction", "TransactionType", "User",
    "InsufficientHoldingsError", "compute_metrics", "filter_values",
    "has_nav_history", "mutual_fund_detail", "mutual_fund_detail_by_name", "match_mutual_fund_codes",
    "mutual_fund_detail_enriched", "mutual_fund_history", "mutual_fund_similar",
    "mutual_fund_similar_enriched", "mutual_fund_screen", "mutual_fund_compare",
    "mutual_fund_holdings_snapshot", "mutual_fund_overlap", "mutual_fund_managers",
    "mutual_funds", "stock_categories",
    "stock_compare", "stock_daily_metrics", "stock_detail", "stock_detail_enriched",
    "stock_fundamentals", "stock_fundamentals_summary", "stock_history", "stock_peers",
    "stock_shareholding", "stock_technical_indicators", "stock_valuation", "stocks", "sync_nav",
    "sync_stock_fundamentals", "recompute_metrics", "sync_benchmark", "sync_enrichment",
    "sync_holdings", "sync_managers",
    "mutual_fund_metric_snapshots", "mutual_fund_enrichment", "mutual_fund_benchmark",
    "mutual_fund_benchmark_history", "benchmark_list", "benchmark_history", "benchmark_snapshot",
    "sync_home_indexes",
    "METRIC_PERIODS", "SCREEN_SORT_COLUMNS",
    "STOCK_SCREEN_SORT_COLUMNS", "stock_screen",
    "list_screens", "refresh_screens", "run_screen",
]
