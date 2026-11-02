from fastapi import FastAPI

from .market_data_routes import router as market_data_router
from .portfolio_routes import router as portfolio_router

app = FastAPI(title="Wealth Orbit API", version="1.0.0")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "wealth-orbit-api"}


app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")
