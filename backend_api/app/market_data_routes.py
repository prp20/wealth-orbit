import sys
from pathlib import Path
from fastapi import APIRouter, Query

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
from backend.reference_service import mutual_funds, mutual_fund_detail, stock_categories, stock_detail, stocks  # noqa: E402

router = APIRouter(prefix="/market-data", tags=["market-data"])

@router.get("/mutual-funds")
def mutual_fund_list(search: str = Query(""), category: str = Query("All")):
    return mutual_funds(search, category).to_dict(orient="records")

@router.get("/stocks")
def stock_list(search: str = Query(""), sector: str = Query("All")):
    return stocks(search, sector).to_dict(orient="records")

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
