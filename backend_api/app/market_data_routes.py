from fastapi import APIRouter, Query, HTTPException
from datetime import date

from .portfolio_backend import (filter_values, mutual_funds, mutual_fund_detail,
    mutual_fund_detail_by_name, mutual_fund_history, stock_categories, stock_detail,
    stock_detail_enriched, stock_peers, stock_compare, stock_fundamentals_summary,
    mutual_fund_metric_snapshots, mutual_fund_enrichment,
    mutual_fund_benchmark, mutual_fund_benchmark_history,
    benchmark_list, benchmark_history,
    stock_history, stocks, stock_daily_metrics, stock_fundamentals,
    stock_shareholding, stock_technical_indicators, sync_stock_fundamentals, mutual_fund_similar,
    compute_metrics, has_nav_history, sync_nav, recompute_metrics, sync_benchmark, sync_enrichment)
from .sync_queue import enqueue, get_job, list_jobs, latest_job, latest_jobs_by_kind

STOCK_SYNC_KINDS = ("PRICES", "TECHNICAL", "FUNDAMENTALS", "DAILY_METRICS", "SHAREHOLDING")

router = APIRouter(prefix="/market-data", tags=["market-data"])

@router.get("/sync/queue")
def sync_queue(include_history: bool = Query(False)):
    return {"jobs": list_jobs(include_history)}

@router.get("/sync/jobs/{job_id}")
def sync_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job

@router.post("/stocks/{symbol}/sync")
def sync_stock(symbol: str, kind: str = Query("technical"), force: bool = Query(False), from_date: date | None = None, to_date: date | None = None):
    """Return a sync request acknowledgement; ingestion workers can consume this request."""
    kind = kind.lower()
    if kind not in {"prices", "technical", "fundamentals", "daily_metrics", "shareholding"}:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    if stock_detail(symbol) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    if kind == "fundamentals" or kind == "shareholding":
        work = lambda: sync_stock_fundamentals(symbol, force)
    else:
        from backend.market_data.sync import sync_daily_metrics, sync_technical_indicators, sync_prices
        work = (lambda: sync_daily_metrics(symbol, force)) if kind == "daily_metrics" else (lambda: sync_technical_indicators(symbol, force))
        if kind == "prices":
            work = lambda: sync_prices(symbol, force, from_date, to_date)
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
def sync_mutual_fund(scheme_code: str, force: bool = Query(False), from_date: date | None = None, to_date: date | None = None):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    job, created = enqueue("MUTUAL_FUND", scheme_code, "NAV", force, lambda: sync_nav(scheme_code, force, from_date, to_date))
    return {**job, "duplicate": not created}

@router.get("/mutual-funds/{scheme_code}/sync/status")
def sync_mutual_fund_status(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    job = latest_job("MUTUAL_FUND", scheme_code, "NAV")
    if not job:
        return {"status": "idle", "kind": "nav", "job": None}
    return {"status": job.get("status", "idle").lower(), "kind": "nav", "job": job}

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
    return mutual_fund_similar(scheme_code).to_dict(orient="records")

@router.get("/mutual-funds/{scheme_code}/enrichment")
def mutual_fund_enrichment_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_enrichment(scheme_code)

@router.get("/mutual-funds/{scheme_code}/benchmark")
def mutual_fund_benchmark_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_benchmark(scheme_code) or {"available": False, "reason": "No benchmark is mapped"}

@router.get("/mutual-funds/{scheme_code}/benchmark/history")
def mutual_fund_benchmark_history_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_benchmark_history(scheme_code)

@router.post("/mutual-funds/{scheme_code}/sync/nav")
def mutual_fund_nav_sync(scheme_code: str, force: bool = Query(False), from_date: date | None = None, to_date: date | None = None):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_NAV", force, lambda: sync_nav(scheme_code, force, from_date, to_date))
    return {**job, "duplicate": not created}

@router.post("/mutual-funds/{scheme_code}/sync/metrics")
def mutual_fund_metrics_sync(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    if not has_nav_history(scheme_code):
        raise HTTPException(
            status_code=409,
            detail="NAV history is not available. Complete a successful NAV sync before queuing metrics.",
        )
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_METRICS", force, lambda: recompute_metrics(scheme_code, force))
    return {**job, "duplicate": not created}

@router.post("/mutual-funds/{scheme_code}/sync/benchmark")
def mutual_fund_benchmark_sync(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_BENCHMARK", force, lambda: sync_benchmark(scheme_code, force))
    return {**job, "duplicate": not created}

@router.post("/mutual-funds/{scheme_code}/sync/enrichment")
def mutual_fund_enrichment_sync(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_ENRICHMENT", force, lambda: sync_enrichment(scheme_code, force))
    return {**job, "duplicate": not created}

@router.get("/mutual-funds")
def mutual_fund_list(search: str = Query(""), amc: str = Query("All"), category: str = Query("All"), subcategory: str = Query("All"), plan_type: str = Query("All"), option_type: str = Query("All")):
    return mutual_funds(search, amc, category, subcategory, plan_type, option_type).to_dict(orient="records")

@router.get("/benchmarks")
def benchmark_list_route():
    return benchmark_list()

@router.get("/benchmarks/{index_code}/history")
def benchmark_history_route(index_code: str):
    return benchmark_history(index_code)

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
    result = mutual_fund_detail(scheme_code)
    if result is None: return {"detail": "Mutual fund not found"}
    return result

@router.get("/mutual-funds/by-name/{scheme_name:path}")
def mutual_fund_by_name(scheme_name: str):
    result = mutual_fund_detail_by_name(scheme_name)
    if result is None: return {"detail": "Mutual fund not found"}
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
