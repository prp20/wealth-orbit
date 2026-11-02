from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .market_data_routes import router as market_data_router
from .portfolio_routes import router as portfolio_router

app = FastAPI(title="Wealth Orbit API", version="1.0.0")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "wealth-orbit-api"}


app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")

UI_DIST = Path(__file__).resolve().parents[2] / "frontend-react" / "dist"
if UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIST, html=True), name="ui")
