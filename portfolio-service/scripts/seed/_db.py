"""Shared database helpers for market-data seed scripts."""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import register_uuid

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = ROOT / "data" / "seed"
SEED_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT / ".env")
register_uuid()


def ensure_project_paths() -> None:
    """Make portfolio-service importable as ``backend.*`` and seed helpers as siblings."""
    portfolio_root = ROOT / "portfolio-service"
    for path in (str(ROOT), str(portfolio_root), str(SEED_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


ensure_project_paths()


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("ERROR: DATABASE_URL environment variable is not set.")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")


def connect():
    return psycopg2.connect(database_url(), connect_timeout=30)


def resolve_data_dir(data_dir: Path | str | None) -> Path:
    path = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def get_or_create_source(cur, source_name: str) -> uuid.UUID:
    from backend.market_data.sources import ensure_data_source

    return ensure_data_source(cur, source_name)
