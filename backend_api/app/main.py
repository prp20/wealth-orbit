from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from backend_api.app.auth import ensure_password_column
from backend_api.app.auth_routes import router as auth_router
from backend_api.app.logging_config import configure_logging
from backend_api.app.market_data_routes import router as market_data_router
from backend_api.app.portfolio_routes import router as portfolio_router

app = FastAPI(title="Wealth Orbit API", version="1.0.0")
configure_logging()


@app.on_event("startup")
def prepare_local_auth():
    ensure_password_column()

@app.middleware("http")
async def no_cache_ui(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "wealth-orbit-api"}


@app.get("/portfolio", include_in_schema=False)
@app.get("/transactions", include_in_schema=False)
@app.get("/mutualfunds", include_in_schema=False)
@app.get("/stocks", include_in_schema=False)
def legacy_ui_redirect(request: Request):
    return RedirectResponse(url=f"/ui{request.url.path}", status_code=307)


app.include_router(auth_router, prefix="/api/v1")
app.include_router(portfolio_router, prefix="/api/v1")
app.include_router(market_data_router, prefix="/api/v1")

UI_DIST = Path(__file__).resolve().parents[2] / "frontend-react" / "dist"

@app.get("/ui", include_in_schema=False)
def ui_root():
    return RedirectResponse(url="/ui/", status_code=307)

@app.get("/ui/{path:path}", include_in_schema=False)
def ui_spa_fallback(path: str):
    asset = UI_DIST / path
    if path and asset.is_file():
        return FileResponse(asset)
    return FileResponse(UI_DIST / "index.html")

if UI_DIST.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIST, html=True), name="ui-assets")
