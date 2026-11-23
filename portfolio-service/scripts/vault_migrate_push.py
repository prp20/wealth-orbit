#!/usr/bin/env python3
"""Push local SQLite portfolio into encrypted public.portfolio_vault via session pooler.

Requires env:
  DATABASE_URL, PORTFOLIO_ENCRYPTION_SECRET, VAULT_USER_ID, PORTFOLIO_SQLITE_URL

Usage:
  uv run python portfolio-service/scripts/vault_migrate_push.py
  uv run python portfolio-service/scripts/vault_migrate_push.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.models import Portfolio, User  # noqa: E402
from backend.vault.crypto import encrypt_snapshot  # noqa: E402
from backend.vault.repository import (  # noqa: E402
    VaultConfigError,
    encryption_secret,
    get_vault,
    put_vault,
    vault_user_id,
)
from backend.vault.schema import snapshot_to_json  # noqa: E402
from backend.vault.sqlite_export import export_portfolio_from_sqlite  # noqa: E402


def portfolio_sqlite_url() -> str:
    return os.environ.get(
        "PORTFOLIO_SQLITE_URL", "sqlite:///./portfolio-service/portfolio.db"
    ).replace("sqlite+aiosqlite://", "sqlite://")


async def _export_first_portfolio() -> tuple[str, object]:
    sync_url = portfolio_sqlite_url()
    engine = create_engine(sync_url)
    with Session(engine) as session:
        portfolio = session.scalar(select(Portfolio).limit(1))
        if portfolio is None:
            raise SystemExit("No portfolio rows in local SQLite")
        portfolio_id = portfolio.portfolio_id
        user = session.get(User, portfolio.user_id)
        label = user.full_name if user else str(portfolio.user_id)
    engine.dispose()

    async_url = sync_url.replace("sqlite://", "sqlite+aiosqlite://")
    aengine = create_async_engine(async_url)
    factory = async_sessionmaker(aengine, expire_on_commit=False)
    async with factory() as session:
        snap = await export_portfolio_from_sqlite(session, portfolio_id)
    await aengine.dispose()
    return label, snap


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Export and print counts without writing to Postgres",
    )
    args = parser.parse_args()

    try:
        secret = encryption_secret()
        uid = vault_user_id()
    except VaultConfigError as exc:
        raise SystemExit(str(exc)) from exc

    label, snap = asyncio.run(_export_first_portfolio())
    plain = snapshot_to_json(snap)
    print(f"User/portfolio: {label}")
    print(f"VAULT_USER_ID: {uid}")
    print(
        f"assets={len(snap.assets)} holdings={len(snap.holdings)} "
        f"transactions={len(snap.transactions)} json_bytes={len(plain)}"
    )
    if args.dry_run:
        print("Dry run: not writing to portfolio_vault")
        return

    existing = get_vault(uid)
    generation = existing.vault_generation if existing else 1
    expected = existing.version if existing else 0
    ciphertext = encrypt_snapshot(
        plain, secret=secret, user_id=uid, vault_generation=generation
    )
    row = put_vault(
        ciphertext=ciphertext,
        expected_version=expected,
        vault_generation=generation,
        user_id=uid,
    )
    print(
        f"Wrote vault version={row.version} generation={row.vault_generation} "
        f"ciphertext_len={len(row.ciphertext)}"
    )


if __name__ == "__main__":
    main()
