import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.market_data.sources import ensure_data_source

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _url() -> str:
    raw = os.environ.get("DATABASE_URL", "")
    return raw.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")


def test_concurrent_ensure_reuses_one_source_row():
    database_url = _url()
    if not database_url.startswith("postgres"):
        pytest.skip("DATABASE_URL is not set")
    name = f"race-source-{uuid4().hex}"
    errors: list[str] = []
    ids: list[str] = []

    def worker():
        try:
            with psycopg2.connect(database_url, connect_timeout=8) as conn:
                with conn.cursor() as cur:
                    ids.append(str(ensure_data_source(cur, name)))
                conn.commit()
        except Exception as exc:
            errors.append(str(exc).split("\n", 1)[0])

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: worker(), range(8)))

    with psycopg2.connect(database_url, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM market_data.data_sources WHERE source_name=%s", (name,))
        conn.commit()

    assert errors == []
    assert len(ids) == 8
    assert len(set(ids)) == 1
