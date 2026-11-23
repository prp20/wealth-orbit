from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from backend_api.app.auth import current_user
from backend_api.app.dependencies import portfolio_session, portfolio_url

# portfolio-service on path for vault helpers
_PS = Path(__file__).resolve().parents[2] / "portfolio-service"
if str(_PS) not in sys.path:
    sys.path.insert(0, str(_PS))

from backend.models import Portfolio, User  # noqa: E402
from backend.vault.crypto import decrypt_snapshot, encrypt_snapshot  # noqa: E402
from backend.vault.repository import (  # noqa: E402
    VaultConfigError,
    VaultConflictError,
    encryption_secret,
    get_vault,
    put_vault,
    reset_vault,
    vault_user_id,
)
from backend.vault.schema import snapshot_to_json  # noqa: E402
from backend.vault.sqlite_export import export_portfolio_from_sqlite  # noqa: E402

router = APIRouter(prefix="/vault", tags=["vault"])


class VaultPutBody(BaseModel):
    version: int = Field(ge=0, description="0 to create; otherwise current remote version")
    ciphertext: str = Field(min_length=1)
    vault_generation: int = Field(ge=1, default=1)


class VaultResetBody(BaseModel):
    confirm: str


def _row_payload(row) -> dict:
    return {
        "user_id": row.user_id,
        "vault_generation": row.vault_generation,
        "version": row.version,
        "ciphertext": row.ciphertext,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def read_vault(user: User = Depends(current_user)):
    try:
        row = get_vault()
    except VaultConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Vault not found")
    return _row_payload(row)


@router.put("")
def write_vault(body: VaultPutBody, user: User = Depends(current_user)):
    try:
        row = put_vault(
            ciphertext=body.ciphertext,
            expected_version=body.version,
            vault_generation=body.vault_generation,
        )
    except VaultConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VaultConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _row_payload(row)


@router.post("/reset")
def vault_reset(body: VaultResetBody, user: User = Depends(current_user)):
    if body.confirm != "RESET":
        raise HTTPException(status_code=400, detail='confirm must be exactly "RESET"')
    try:
        result = reset_vault()
    except VaultConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "ok": True,
        "vault_generation": result["vault_generation"],
        "version": result["version"],
        "message": "Vault deleted. Set a new PORTFOLIO_ENCRYPTION_SECRET in .env, then push again.",
    }


@router.post("/push-from-sqlite")
async def push_from_sqlite(
    user: User = Depends(current_user),
    session: Session = Depends(portfolio_session),
):
    """Export local SQLite portfolio, encrypt, upsert into portfolio_vault."""
    try:
        secret = encryption_secret()
        uid = vault_user_id()
    except VaultConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    portfolio = session.scalar(select(Portfolio).where(Portfolio.user_id == user.user_id))
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Local portfolio not found")

    sqlite_url = portfolio_url().replace("sqlite://", "sqlite+aiosqlite://")
    engine = create_async_engine(sqlite_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as async_session:
        snap = await export_portfolio_from_sqlite(async_session, portfolio.portfolio_id)
    await engine.dispose()

    plain = snapshot_to_json(snap)
    existing = get_vault(uid)
    generation = existing.vault_generation if existing else 1
    expected = existing.version if existing else 0
    ciphertext = encrypt_snapshot(
        plain, secret=secret, user_id=uid, vault_generation=generation
    )
    try:
        row = put_vault(
            ciphertext=ciphertext,
            expected_version=expected,
            vault_generation=generation,
            user_id=uid,
        )
    except VaultConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "ok": True,
        "vault": _row_payload(row),
        "holdings_count": len(snap.holdings),
        "transactions_count": len(snap.transactions),
    }


@router.get("/pull-summary")
def pull_summary(user: User = Depends(current_user)):
    """Decrypt vault and return non-sensitive counts (never log plaintext)."""
    try:
        secret = encryption_secret()
        uid = vault_user_id()
        row = get_vault(uid)
    except VaultConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Vault not found")
    try:
        plain = decrypt_snapshot(
            row.ciphertext,
            secret=secret,
            user_id=uid,
            vault_generation=row.vault_generation,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Decrypt failed; check PORTFOLIO_ENCRYPTION_SECRET and vault_generation",
        ) from exc
    import json

    data = json.loads(plain)
    return {
        "vault_generation": row.vault_generation,
        "version": row.version,
        "schema_version": data.get("schema_version"),
        "portfolio_id": data.get("portfolio_id"),
        "assets_count": len(data.get("assets") or []),
        "holdings_count": len(data.get("holdings") or []),
        "transactions_count": len(data.get("transactions") or []),
        "exported_at": data.get("exported_at"),
    }
