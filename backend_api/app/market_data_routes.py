import sys
from pathlib import Path
from fastapi import APIRouter, Query

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
from backend.reference_service import filter_values, mutual_funds, mutual_fund_detail, mutual_fund_detail_by_name, stock_categories, stock_detail, stocks  # noqa: E402

router = APIRouter(prefix="/market-data", tags=["market-data"])

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
