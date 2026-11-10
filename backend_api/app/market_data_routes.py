from fastapi import APIRouter, Query, HTTPException
from datetime import date
from pydantic import BaseModel, Field

from .portfolio_backend import (filter_values, mutual_funds, mutual_fund_detail,
    mutual_fund_detail_by_name, mutual_fund_detail_enriched, mutual_fund_history,
    stock_categories, stock_detail,
    stock_detail_enriched, stock_peers, stock_compare, stock_fundamentals_summary,
    stock_valuation,
    mutual_fund_metric_snapshots, mutual_fund_enrichment,
    mutual_fund_benchmark, mutual_fund_benchmark_history,
    benchmark_list, benchmark_history, benchmark_snapshot, sync_home_indexes,
    stock_history, stocks, stock_daily_metrics, stock_fundamentals,
    stock_shareholding, stock_technical_indicators, sync_stock_fundamentals,
    mutual_fund_similar_enriched, mutual_fund_screen, mutual_fund_compare,
    mutual_fund_holdings_snapshot, mutual_fund_overlap, mutual_fund_managers,
    compute_metrics, has_nav_history, sync_nav, recompute_metrics, sync_benchmark, sync_enrichment,
    sync_holdings, sync_managers,
    METRIC_PERIODS, SCREEN_SORT_COLUMNS)
from .sync_queue import enqueue, get_job, list_jobs, latest_job, latest_jobs_by_kind

STOCK_SYNC_KINDS = ("PRICES", "TECHNICAL", "FUNDAMENTALS", "DAILY_METRICS", "SHAREHOLDING")
MF_SYNC_KINDS = ("MF_NAV", "MF_METRICS", "MF_BENCHMARK", "MF_ENRICHMENT", "MF_HOLDINGS", "MF_MANAGERS")
MF_KIND_ALIASES = {
    "nav": "MF_NAV",
    "metrics": "MF_METRICS",
    "benchmark": "MF_BENCHMARK",
    "enrichment": "MF_ENRICHMENT",
    "holdings": "MF_HOLDINGS",
    "managers": "MF_MANAGERS",
}

router = APIRouter(prefix="/market-data", tags=["market-data"])


class TrackStockBody(BaseModel):
    trading_symbol: str = Field(min_length=1, max_length=32)


class TrackFundBody(BaseModel):
    scheme_code: str = Field(min_length=1, max_length=12)


class TrackIndexBody(BaseModel):
    index_code: str = Field(min_length=1, max_length=32)
    yf_symbol: str | None = Field(default=None, max_length=32)


def _instrument_http_error(exc: Exception) -> HTTPException:
    from backend.market_data.instrument_registry import InstrumentResolveError

    if isinstance(exc, InstrumentResolveError):
        return HTTPException(
            status_code=422,
            detail={"reason": exc.reason, "message": exc.message},
        )
    return HTTPException(status_code=422, detail={"reason": "track_failed", "message": "Could not add instrument"})


def _parse_history_period(raw: str | None, *, default: str | None = "5y") -> str | None:
    from backend.market_data.history_period import normalize_history_period

    try:
        return normalize_history_period(raw, default=default)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"reason": "invalid_history_period", "message": str(exc)},
        ) from None


def _mf_sync_type(kind: str) -> str:
    key = kind.lower().strip()
    if key not in MF_KIND_ALIASES:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    return MF_KIND_ALIASES[key]


def _enqueue_mf_sync(
    scheme_code: str,
    kind: str,
    force: bool,
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = None,
):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    sync_type = _mf_sync_type(kind)
    if sync_type == "MF_NAV":
        work = lambda: sync_nav(
            scheme_code,
            force,
            from_date,
            to_date,
            history_period=history_period,
        )
    elif sync_type == "MF_METRICS":
        if not has_nav_history(scheme_code):
            raise HTTPException(
                status_code=409,
                detail="NAV history is not available. Complete a successful NAV sync before queuing metrics.",
            )
        work = lambda: recompute_metrics(scheme_code, force)
    elif sync_type == "MF_BENCHMARK":
        work = lambda: sync_benchmark(scheme_code, force)
    elif sync_type == "MF_ENRICHMENT":
        work = lambda: sync_enrichment(scheme_code, force)
    elif sync_type == "MF_HOLDINGS":
        work = lambda: sync_holdings(scheme_code, force)
    elif sync_type == "MF_MANAGERS":
        work = lambda: sync_managers(scheme_code, force)
    else:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    job, created = enqueue("MUTUAL_FUND", scheme_code, sync_type, force, work)
    return {**job, "duplicate": not created}

@router.get("/sync/queue")
def sync_queue(include_history: bool = Query(False), limit: int = Query(25, ge=1, le=100)):
    # Read-only: does not run stale recovery (that happens on enqueue).
    # Auth/rate-limit for sync enqueue remains a post-1.4 hardening item.
    return {"jobs": list_jobs(include_history, limit)}

@router.get("/sync/jobs/{job_id}")
def sync_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job

@router.post("/stocks/{symbol}/sync")
def sync_stock(
    symbol: str,
    kind: str = Query("technical"),
    force: bool = Query(False),
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = Query(None),
):
    """Return a sync request acknowledgement; ingestion workers can consume this request."""
    kind = kind.lower()
    if kind not in {"prices", "technical", "fundamentals", "daily_metrics", "shareholding"}:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    if stock_detail(symbol) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    period = _parse_history_period(history_period, default=None) if history_period else None
    if kind == "fundamentals" or kind == "shareholding":
        work = lambda: sync_stock_fundamentals(symbol, force)
    else:
        from backend.market_data.sync import sync_daily_metrics, sync_technical_indicators, sync_prices
        work = (lambda: sync_daily_metrics(symbol, force)) if kind == "daily_metrics" else (lambda: sync_technical_indicators(symbol, force))
        if kind == "prices":
            work = lambda: sync_prices(symbol, force, from_date, to_date, history_period=period)
    job, created = enqueue("STOCK", symbol, kind.upper(), force, work)
    return {**job, "duplicate": not created}

@router.get("/stocks/{symbol}/sync/status")
def sync_stock_status(symbol: str, kind: str = Query("fundamentals"), force: bool = Query(False)):
    kind = kind.lower()
    if kind not in {"prices", "technical", "fundamentals", "daily_metrics", "shareholding"}:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    if stock_detail(symbol) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    job = latest_job("STOCK", symbol, kind.upper())
    if not job:
        return {"status": "idle", "kind": kind, "job": None}
    return {"status": job.get("status", "idle").lower(), "kind": kind, "job": job}

@router.post("/mutual-funds/{scheme_code}/sync")
def sync_mutual_fund(
    scheme_code: str,
    kind: str = Query("nav"),
    force: bool = Query(False),
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = Query(None),
):
    period = _parse_history_period(history_period, default=None) if history_period else None
    return _enqueue_mf_sync(scheme_code, kind, force, from_date, to_date, history_period=period)

@router.get("/mutual-funds/{scheme_code}/sync/status")
def sync_mutual_fund_status(scheme_code: str, kind: str = Query("nav"), force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    sync_type = _mf_sync_type(kind)
    job = latest_job("MUTUAL_FUND", scheme_code, sync_type)
    if not job:
        return {"status": "idle", "kind": kind.lower(), "job": None}
    return {"status": job.get("status", "idle").lower(), "kind": kind.lower(), "job": job}

@router.get("/mutual-funds/{scheme_code}/metrics")
def mutual_fund_metrics(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    try:
        from backend.reference_service import mutual_fund_metric_snapshots
        rows = mutual_fund_metric_snapshots(scheme_code)
        return rows if rows else compute_metrics(scheme_code)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/mutual-funds/{scheme_code}/similar")
def mutual_fund_similar_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_similar_enriched(scheme_code)

@router.get("/mutual-funds/{scheme_code}/enrichment")
def mutual_fund_enrichment_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_enrichment(scheme_code)

@router.get("/mutual-funds/{scheme_code}/benchmark")
def mutual_fund_benchmark_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_benchmark(scheme_code) or {"available": False, "reason": "No benchmark is mapped"}

@router.get("/mutual-funds/{scheme_code}/benchmark/history")
def mutual_fund_benchmark_history_route(
    scheme_code: str,
    from_date: date | None = None,
    to_date: date | None = None,
):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    rows = mutual_fund_benchmark_history(scheme_code)
    if from_date or to_date:
        filtered = []
        for row in rows:
            value = row.get("date")
            if value is None:
                continue
            as_date = value if isinstance(value, date) else date.fromisoformat(str(value)[:10])
            if from_date and as_date < from_date:
                continue
            if to_date and as_date > to_date:
                continue
            filtered.append(row)
        return filtered
    return rows

@router.post("/mutual-funds/{scheme_code}/sync/nav")
def mutual_fund_nav_sync(
    scheme_code: str,
    force: bool = Query(False),
    from_date: date | None = None,
    to_date: date | None = None,
    history_period: str | None = Query(None),
):
    period = _parse_history_period(history_period, default=None) if history_period else None
    return _enqueue_mf_sync(scheme_code, "nav", force, from_date, to_date, history_period=period)

@router.post("/mutual-funds/{scheme_code}/sync/metrics")
def mutual_fund_metrics_sync(scheme_code: str, force: bool = Query(False)):
    return _enqueue_mf_sync(scheme_code, "metrics", force)

@router.post("/mutual-funds/{scheme_code}/sync/benchmark")
def mutual_fund_benchmark_sync(scheme_code: str, force: bool = Query(False)):
    return _enqueue_mf_sync(scheme_code, "benchmark", force)

@router.post("/mutual-funds/{scheme_code}/sync/enrichment")
def mutual_fund_enrichment_sync(scheme_code: str, force: bool = Query(False)):
    return _enqueue_mf_sync(scheme_code, "enrichment", force)

@router.post("/mutual-funds/{scheme_code}/sync/holdings")
def mutual_fund_holdings_sync(scheme_code: str, force: bool = Query(False)):
    return _enqueue_mf_sync(scheme_code, "holdings", force)

@router.post("/mutual-funds/{scheme_code}/sync/managers")
def mutual_fund_managers_sync(scheme_code: str, force: bool = Query(False)):
    return _enqueue_mf_sync(scheme_code, "managers", force)

@router.get("/mutual-funds/overlap")
def mutual_fund_overlap_route(scheme_codes: str = Query(..., description="Comma-separated scheme codes")):
    parts = [part.strip() for part in scheme_codes.split(",") if part.strip()]
    if len(parts) < 2:
        raise HTTPException(status_code=422, detail="scheme_codes requires at least 2 codes")
    if len(parts) > 10:
        raise HTTPException(status_code=422, detail="overlap at most 10 schemes")
    try:
        return mutual_fund_overlap(parts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/mutual-funds/{scheme_code}/holdings")
def mutual_fund_holdings_route(scheme_code: str, top_n: int = Query(20, ge=1, le=50)):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_holdings_snapshot(scheme_code, top_n=top_n)

@router.get("/mutual-funds/{scheme_code}/managers")
def mutual_fund_managers_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_managers(scheme_code)

@router.get("/mutual-funds")
def mutual_fund_list(search: str = Query(""), amc: str = Query("All"), category: str = Query("All"), subcategory: str = Query("All"), plan_type: str = Query("All"), option_type: str = Query("All")):
    return mutual_funds(search, amc, category, subcategory, plan_type, option_type).to_dict(orient="records")

@router.get("/mutual-funds/screen")
def mutual_fund_screen_route(
    search: str = Query(""),
    amc: str = Query("All"),
    category: str = Query("All"),
    subcategory: str = Query("All"),
    plan_type: str = Query("All"),
    option_type: str = Query("All"),
    metric_period: str = Query("1Y"),
    min_trailing: float | None = Query(None),
    min_cagr: float | None = Query(None),
    min_sharpe: float | None = Query(None),
    max_drawdown: float | None = Query(None),
    min_aum: float | None = Query(None),
    max_aum: float | None = Query(None),
    max_expense_ratio: float | None = Query(None),
    require_metrics: bool = Query(False),
    sort_by: str = Query("scheme_name"),
    sort_dir: str = Query("asc"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if metric_period not in METRIC_PERIODS:
        raise HTTPException(status_code=422, detail=f"metric_period must be one of {', '.join(METRIC_PERIODS)}")
    if sort_by not in SCREEN_SORT_COLUMNS:
        raise HTTPException(
            status_code=422,
            detail=f"sort_by must be one of {', '.join(SCREEN_SORT_COLUMNS)}",
        )
    try:
        return mutual_fund_screen(
            search=search,
            amc=amc,
            category=category,
            subcategory=subcategory,
            plan_type=plan_type,
            option_type=option_type,
            metric_period=metric_period,
            min_trailing=min_trailing,
            min_cagr=min_cagr,
            min_sharpe=min_sharpe,
            max_drawdown=max_drawdown,
            min_aum=min_aum,
            max_aum=max_aum,
            max_expense_ratio=max_expense_ratio,
            require_metrics=require_metrics,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/mutual-funds/compare")
def mutual_fund_compare_route(
    scheme_codes: str = Query(..., description="Comma-separated scheme codes"),
    metric_period: str = Query("1Y"),
):
    parts = [part.strip() for part in scheme_codes.split(",") if part.strip()]
    if not parts:
        raise HTTPException(status_code=422, detail="scheme_codes is required")
    if len(parts) > 10:
        raise HTTPException(status_code=422, detail="compare at most 10 schemes")
    if metric_period not in METRIC_PERIODS:
        raise HTTPException(status_code=422, detail=f"metric_period must be one of {', '.join(METRIC_PERIODS)}")
    try:
        rows = mutual_fund_compare(parts, metric_period=metric_period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not rows:
        raise HTTPException(status_code=422, detail="no matching mutual funds for scheme_codes")
    return rows

@router.get("/benchmarks")
def benchmark_list_route():
    return benchmark_list()

def _benchmark_codes(codes: str) -> list[str]:
    parts = [part.strip() for part in codes.split(",") if part.strip()]
    if len(parts) > 12:
        raise HTTPException(status_code=422, detail="at most 12 index codes")
    return parts

@router.get("/benchmarks/summary")
def benchmark_summary_route(codes: str = Query("")):
    return benchmark_snapshot(_benchmark_codes(codes))

# The job table only allows STOCK and MUTUAL_FUND. Home indexes share one job row.
HOME_INDEX_ENTITY = "HOME-INDEXES"

@router.post("/benchmarks/sync")
def benchmark_sync_route(codes: str = Query(""), history_period: str | None = Query(None)):
    parts = _benchmark_codes(codes)
    if not parts:
        raise HTTPException(status_code=422, detail="at least one index code is required")
    period = _parse_history_period(history_period, default=None) if history_period else None
    job, created = enqueue(
        "STOCK",
        HOME_INDEX_ENTITY,
        "PRICES",
        False,
        lambda: sync_home_indexes(parts, history_period=period),
    )
    return {**job, "duplicate": not created}

@router.get("/benchmarks/sync/status")
def benchmark_sync_status_route():
    job = latest_job("STOCK", HOME_INDEX_ENTITY, "PRICES")
    if not job:
        return {"status": "idle", "job": None}
    return {"status": str(job.get("status", "idle")).lower(), "job": job}

@router.get("/benchmarks/{index_code}/history")
def benchmark_history_route(index_code: str):
    return benchmark_history(index_code)


@router.get("/instruments/stocks/preview")
def preview_stock_instrument(trading_symbol: str = Query(...)):
    from backend.market_data.instrument_registry import InstrumentResolveError, resolve_stock

    try:
        return resolve_stock(trading_symbol)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None


@router.get("/instruments/mutual-funds/preview")
def preview_fund_instrument(scheme_code: str = Query(...)):
    from backend.market_data.instrument_registry import InstrumentResolveError, resolve_fund

    try:
        return resolve_fund(scheme_code)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None


@router.get("/instruments/indexes/preview")
def preview_index_instrument(index_code: str = Query(...), yf_symbol: str | None = Query(None)):
    from backend.market_data.instrument_registry import InstrumentResolveError, resolve_index

    try:
        return resolve_index(index_code, yf_symbol)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None


@router.post("/instruments/stocks")
def track_stock_instrument(
    body: TrackStockBody,
    enqueue_history: bool = Query(True),
    history_period: str = Query("5y"),
):
    from backend.market_data.instrument_registry import InstrumentResolveError, ensure_stock
    from backend.market_data.sync import sync_prices

    period = _parse_history_period(history_period, default="5y")
    try:
        result = ensure_stock(body.trading_symbol)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None
    jobs = []
    if enqueue_history:
        symbol = result["master"]["trading_symbol"]
        job, created = enqueue(
            "STOCK",
            symbol,
            "PRICES",
            False,
            lambda: sync_prices(symbol, False, history_period=period),
        )
        jobs.append(
            {
                "job_id": job.get("job_id"),
                "kind": "prices",
                "history_period": period,
                "duplicate": not created,
            }
        )
    return {**result, "jobs": jobs, "history_period": period}


@router.post("/instruments/mutual-funds")
def track_fund_instrument(
    body: TrackFundBody,
    enqueue_history: bool = Query(True),
    history_period: str = Query("5y"),
):
    from backend.market_data.instrument_registry import InstrumentResolveError, ensure_fund

    period = _parse_history_period(history_period, default="5y")
    try:
        result = ensure_fund(body.scheme_code)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None
    jobs = []
    if enqueue_history:
        code = result["master"]["scheme_code"]
        job, created = enqueue(
            "MUTUAL_FUND",
            code,
            "MF_NAV",
            False,
            lambda: sync_nav(code, False, history_period=period),
        )
        jobs.append(
            {
                "job_id": job.get("job_id"),
                "kind": "nav",
                "history_period": period,
                "duplicate": not created,
            }
        )
    return {**result, "jobs": jobs, "history_period": period}


@router.post("/instruments/indexes")
def track_index_instrument(
    body: TrackIndexBody,
    enqueue_history: bool = Query(True),
    history_period: str = Query("5y"),
):
    from backend.market_data.instrument_registry import InstrumentResolveError, ensure_index

    period = _parse_history_period(history_period, default="5y")
    try:
        result = ensure_index(body.index_code, body.yf_symbol)
    except InstrumentResolveError as exc:
        raise _instrument_http_error(exc) from None
    jobs = []
    if enqueue_history:
        code = result["master"]["index_code"]
        job, created = enqueue(
            "STOCK",
            HOME_INDEX_ENTITY,
            "PRICES",
            False,
            lambda: sync_home_indexes([code], history_period=period),
        )
        jobs.append(
            {
                "job_id": job.get("job_id"),
                "kind": "index_history",
                "history_period": period,
                "duplicate": not created,
            }
        )
    return {**result, "jobs": jobs, "history_period": period}


@router.get("/stocks")
def stock_list(search: str = Query(""), exchange: str = Query("All"), sector: str = Query("All"), industry: str = Query("All")):
    return stocks(search, exchange, sector, industry).to_dict(orient="records")

@router.get("/filters/{kind}")
def filter_list(kind: str): return filter_values(kind)

@router.get("/sectors")
def sector_list():
    return stock_categories()

@router.get("/stocks/compare")
def stock_compare_route(symbols: str = Query(..., description="Comma-separated trading symbols")):
    parts = [part.strip() for part in symbols.split(",") if part.strip()]
    if not parts:
        raise HTTPException(status_code=422, detail="symbols is required")
    if len(parts) > 20:
        raise HTTPException(status_code=422, detail="compare at most 20 symbols")
    return stock_compare(parts)

@router.get("/stocks/{symbol}")
def stock_item(symbol: str):
    sync_map = latest_jobs_by_kind("STOCK", symbol, STOCK_SYNC_KINDS)
    result = stock_detail_enriched(symbol, sync_map)
    if result is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result

@router.get("/stocks/{symbol}/peers")
def stock_peers_route(symbol: str, by: str = Query("sector"), limit: int = Query(8, ge=1, le=20)):
    result = stock_peers(symbol, by=by, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result

@router.get("/stocks/{symbol}/valuation")
def stock_valuation_route(symbol: str):
    result = stock_valuation(symbol)
    if result is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result

@router.get("/stocks/{symbol}/fundamentals/summary")
def stock_fundamentals_summary_route(
    symbol: str,
    reporting_period: str = Query("ANNUAL"),
    reporting_basis: str = Query("CONSOLIDATED"),
):
    if reporting_period not in {"QUARTERLY", "ANNUAL"}:
        raise HTTPException(status_code=422, detail="reporting_period must be QUARTERLY or ANNUAL")
    if reporting_basis not in {"CONSOLIDATED", "STANDALONE"}:
        raise HTTPException(status_code=422, detail="reporting_basis must be CONSOLIDATED or STANDALONE")
    result = stock_fundamentals_summary(symbol, reporting_period, reporting_basis)
    if result is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return result

@router.get("/mutual-funds/{scheme_code}")
def mutual_fund_item(scheme_code: str):
    sync_map = latest_jobs_by_kind("MUTUAL_FUND", scheme_code, MF_SYNC_KINDS)
    result = mutual_fund_detail_enriched(scheme_code, sync_map)
    if result is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return result

@router.get("/mutual-funds/by-name/{scheme_name:path}")
def mutual_fund_by_name(scheme_name: str):
    base = mutual_fund_detail_by_name(scheme_name)
    if base is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    scheme_code = base.get("scheme_code")
    sync_map = latest_jobs_by_kind("MUTUAL_FUND", scheme_code, MF_SYNC_KINDS)
    result = mutual_fund_detail_enriched(scheme_code, sync_map)
    if result is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    return result

@router.get("/stocks/{symbol}/history")
def stock_history_route(symbol: str, from_date: date | None = None, to_date: date | None = None):
    return stock_history(symbol, from_date, to_date).to_dict(orient="records")

@router.get("/mutual-funds/{scheme_code}/history")
def mutual_fund_history_route(scheme_code: str, from_date: date | None = None, to_date: date | None = None):
    return mutual_fund_history(scheme_code, from_date, to_date).to_dict(orient="records")

@router.get("/stocks/{symbol}/metrics/daily")
def stock_daily_metrics_route(symbol: str, from_date: date | None = None, to_date: date | None = None):
    return stock_daily_metrics(symbol, from_date, to_date).to_dict(orient="records")

@router.get("/stocks/{symbol}/fundamentals")
def stock_fundamentals_route(symbol: str, reporting_period: str = Query(""), reporting_basis: str = Query(""), metric_code: str = Query(""), statement_type: str = Query("")):
    if reporting_period and reporting_period not in {"QUARTERLY", "ANNUAL"}:
        raise HTTPException(status_code=422, detail="reporting_period must be QUARTERLY or ANNUAL")
    if reporting_basis and reporting_basis not in {"CONSOLIDATED", "STANDALONE"}:
        raise HTTPException(status_code=422, detail="reporting_basis must be CONSOLIDATED or STANDALONE")
    if statement_type and statement_type not in {"PL", "BS", "CF", "RATIOS"}:
        raise HTTPException(status_code=422, detail="statement_type must be PL, BS, CF, or RATIOS")
    return stock_fundamentals(symbol, reporting_period, reporting_basis, metric_code, statement_type).to_dict(orient="records")

@router.get("/stocks/{symbol}/shareholding")
def stock_shareholding_route(symbol: str, from_date: date | None = None, to_date: date | None = None):
    return stock_shareholding(symbol, from_date, to_date).to_dict(orient="records")

@router.get("/stocks/{symbol}/technical-indicators")
def stock_technical_route(symbol: str, indicator: str = Query(""), from_date: date | None = None, to_date: date | None = None):
    return stock_technical_indicators(symbol, indicator.upper(), from_date, to_date).to_dict(orient="records")
