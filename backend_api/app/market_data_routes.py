import sys
from pathlib import Path
from fastapi import APIRouter, Query

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
from backend.reference_service import mutual_funds, stock_categories, stocks  # noqa: E402

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
