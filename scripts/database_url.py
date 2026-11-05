"""Choose the database URL Alembic should migrate."""
from __future__ import annotations

DEFAULT_SQLITE = "sqlite:///./portfolio-service/portfolio.db"


def migration_url(environ: dict[str, str], default: str = DEFAULT_SQLITE) -> str:
    url = environ.get("ALEMBIC_DATABASE_URL") or environ.get("DATABASE_URL") or environ.get("PORTFOLIO_SQLITE_URL") or default
    url = url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url
