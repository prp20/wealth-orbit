import sys
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
from backend.reference_service import (filter_values, mutual_funds, mutual_fund_detail,
    mutual_fund_detail_by_name, mutual_fund_history, stock_categories, stock_detail,
    stock_history, stocks, stock_daily_metrics, stock_fundamentals,
    stock_shareholding, stock_technical_indicators, sync_stock_fundamentals, mutual_fund_similar)  # noqa: E402
from .sync_queue import enqueue, get_job, list_jobs

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
def sync_stock(symbol: str, kind: str = Query("technical"), force: bool = Query(False)):
    """Return a sync request acknowledgement; ingestion workers can consume this request."""
    kind = kind.lower()
    if kind not in {"technical", "fundamentals", "daily_metrics", "shareholding"}:
        raise HTTPException(status_code=422, detail="invalid sync kind")
    if stock_detail(symbol) is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    work = (lambda: sync_stock_fundamentals(symbol, force)) if kind in {"fundamentals", "shareholding"} else (lambda: {"status":"completed","symbol":symbol,"kind":kind,"force":force})
    job, created = enqueue("STOCK", symbol, kind.upper(), force, work)
    return {**job, "duplicate": not created}

@router.get("/stocks/{symbol}/sync/status")
def sync_stock_status(symbol: str, kind: str = Query("fundamentals"), force: bool = Query(False)):
    return {"status":"idle"}

@router.post("/mutual-funds/{scheme_code}/sync")
def sync_mutual_fund(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None:
        raise HTTPException(status_code=404, detail="Mutual fund not found")
    from backend.mutual_fund_service import sync_nav
    job, created = enqueue("MUTUAL_FUND", scheme_code, "NAV", force, lambda: sync_nav(scheme_code, force))
    return {**job, "duplicate": not created}

@router.get("/mutual-funds/{scheme_code}/sync/status")
def sync_mutual_fund_status(scheme_code: str, force: bool = Query(False)):
    return {"status":"idle"}

@router.get("/mutual-funds/{scheme_code}/metrics")
def mutual_fund_metrics(scheme_code: str):
    from backend.mutual_fund_service import compute_metrics
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    try:
        return compute_metrics(scheme_code)
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.get("/mutual-funds/{scheme_code}/similar")
def mutual_fund_similar_route(scheme_code: str):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    return mutual_fund_similar(scheme_code).to_dict(orient="records")

@router.post("/mutual-funds/{scheme_code}/sync/nav")
def mutual_fund_nav_sync(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    from backend.mutual_fund_service import sync_nav
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_NAV", force, lambda: sync_nav(scheme_code, force))
    return {**job, "duplicate": not created}

@router.post("/mutual-funds/{scheme_code}/sync/metrics")
def mutual_fund_metrics_sync(scheme_code: str, force: bool = Query(False)):
    if mutual_fund_detail(scheme_code) is None: raise HTTPException(status_code=404, detail="Mutual fund not found")
    from backend.mutual_fund_service import compute_metrics, has_nav_history
    if not has_nav_history(scheme_code):
        raise HTTPException(
            status_code=409,
            detail="NAV history is not available. Complete a successful NAV sync before queuing metrics.",
        )
    job, created = enqueue("MUTUAL_FUND", scheme_code, "MF_METRICS", force, lambda: compute_metrics(scheme_code))
    return {**job, "duplicate": not created}

@router.get("/mutual-funds")
def mutual_fund_list(search: str = Query(""), amc: str = Query("All"), category: str = Query("All"), subcategory: str = Query("All"), plan_type: str = Query("All"), option_type: str = Query("All")):
    return mutual_funds(search, amc, category, subcategory, plan_type, option_type).to_dict(orient="records")

@router.get("/stocks")
def stock_list(search: str = Query(""), exchange: str = Query("All"), sector: str = Query("All"), industry: str = Query("All")):
    return stocks(search, exchange, sector, industry).to_dict(orient="records")

@router.get("/filters/{kind}")
def filter_list(kind: str): return filter_values(kind)

@router.get("/sectors")
def sector_list():
    return stock_categories()

@router.get("/stocks/{symbol}")
def stock_item(symbol: str):
    result = stock_detail(symbol)
    if result is None: return {"detail": "Stock not found"}
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
def stock_fundamentals_route(symbol: str, reporting_period: str = Query(""), reporting_basis: str = Query(""), metric_code: str = Query("")):
    if reporting_period and reporting_period not in {"QUARTERLY", "ANNUAL"}:
        raise HTTPException(status_code=422, detail="reporting_period must be QUARTERLY or ANNUAL")
    if reporting_basis and reporting_basis not in {"CONSOLIDATED", "STANDALONE"}:
        raise HTTPException(status_code=422, detail="reporting_basis must be CONSOLIDATED or STANDALONE")
    return stock_fundamentals(symbol, reporting_period, reporting_basis, metric_code).to_dict(orient="records")

@router.get("/stocks/{symbol}/shareholding")
def stock_shareholding_route(symbol: str, from_date: date | None = None, to_date: date | None = None):
    return stock_shareholding(symbol, from_date, to_date).to_dict(orient="records")

@router.get("/stocks/{symbol}/technical-indicators")
def stock_technical_route(symbol: str, indicator: str = Query(""), from_date: date | None = None, to_date: date | None = None):
    return stock_technical_indicators(symbol, indicator.upper(), from_date, to_date).to_dict(orient="records")
