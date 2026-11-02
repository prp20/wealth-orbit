# Wealth Orbit FastAPI backend

Run from the repository root:

```bash
uvicorn backend_api.app.main:app --reload
```

The API exposes `/api/v1/health`, `/api/v1/portfolios`, `/api/v1/market-data/mutual-funds`, `/api/v1/market-data/stocks`, and `/api/v1/market-data/sectors`. Portfolio endpoints use local SQLite; market-data endpoints use Supabase through `DATABASE_URL`.
