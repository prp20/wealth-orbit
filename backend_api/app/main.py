from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.routing import Mount
from fastapi import Request
from pathlib import Path

from .market_data_routes import router as market_data_router
from .portfolio_routes import router as portfolio_router
from .logging_config import configure_logging

app = FastAPI(title="Wealth Orbit API", version="1.0.0")
configure_logging()

@app.middleware("http")
async def no_cache_ui(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "wealth-orbit-api"}


app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")

UI_DIST = Path(__file__).resolve().parents[2] / "frontend-react" / "dist"
@app.get("/ui", include_in_schema=False)
@app.get("/ui/{path:path}", include_in_schema=False)
def ui_spa_fallback(path: str):
    asset = UI_DIST / path
    if asset.is_file():
        return FileResponse(asset)
    return FileResponse(UI_DIST / "index.html")

if UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIST, html=True), name="ui-assets")
