from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor


class VaultConflictError(Exception):
    """Remote version does not match the expected version."""


class VaultConfigError(Exception):
    """Missing DATABASE_URL or VAULT_USER_ID."""


@dataclass
class VaultRow:
    user_id: str
    vault_generation: int
    version: int
    ciphertext: str
    updated_at: datetime | None


def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_DATABASE_URL")
    if not url:
        raise VaultConfigError("DATABASE_URL is not set")
    return url


def vault_user_id() -> str:
    value = os.environ.get("VAULT_USER_ID", "").strip()
    if not value:
        raise VaultConfigError("VAULT_USER_ID is not set")
    UUID(value)  # validate
    return value


def encryption_secret() -> str:
    secret = os.environ.get("PORTFOLIO_ENCRYPTION_SECRET", "").strip()
    if not secret:
        raise VaultConfigError("PORTFOLIO_ENCRYPTION_SECRET is not set")
    return secret


def _connect():
    return psycopg2.connect(database_url(), connect_timeout=15)


def get_vault(user_id: str | None = None) -> VaultRow | None:
    uid = user_id or vault_user_id()
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT user_id::text AS user_id, vault_generation, version, ciphertext, updated_at
                FROM public.portfolio_vault
                WHERE user_id = %s::uuid
                """,
                (uid,),
            )
            row: dict[str, Any] | None = cur.fetchone()
    if row is None:
        return None
    return VaultRow(
        user_id=row["user_id"],
        vault_generation=int(row["vault_generation"]),
        version=int(row["version"]),
        ciphertext=row["ciphertext"],
        updated_at=row["updated_at"],
    )


def put_vault(
    *,
    ciphertext: str,
    expected_version: int,
    vault_generation: int,
    user_id: str | None = None,
) -> VaultRow:
    """Insert or update with optimistic concurrency on version."""
    uid = user_id or vault_user_id()
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT version, vault_generation FROM public.portfolio_vault
                WHERE user_id = %s::uuid
                """,
                (uid,),
            )
            existing = cur.fetchone()
            if existing is None:
                if expected_version != 0:
                    raise VaultConflictError("vault missing; use expected_version=0 to create")
                cur.execute(
                    """
                    INSERT INTO public.portfolio_vault
                      (user_id, vault_generation, version, ciphertext, updated_at)
                    VALUES (%s::uuid, %s, 1, %s, now())
                    RETURNING user_id::text AS user_id, vault_generation, version, ciphertext, updated_at
                    """,
                    (uid, vault_generation, ciphertext),
                )
            else:
                current_version = int(existing["version"])
                if current_version != expected_version:
                    raise VaultConflictError(
                        f"stale version: expected {expected_version}, remote {current_version}"
                    )
                cur.execute(
                    """
                    UPDATE public.portfolio_vault
                    SET version = %s,
                        vault_generation = %s,
                        ciphertext = %s,
                        updated_at = now()
                    WHERE user_id = %s::uuid AND version = %s
                    RETURNING user_id::text AS user_id, vault_generation, version, ciphertext, updated_at
                    """,
                    (expected_version + 1, vault_generation, ciphertext, uid, expected_version),
                )
            row = cur.fetchone()
            if row is None:
                raise VaultConflictError("concurrent update")
            conn.commit()
    return VaultRow(
        user_id=row["user_id"],
        vault_generation=int(row["vault_generation"]),
        version=int(row["version"]),
        ciphertext=row["ciphertext"],
        updated_at=row["updated_at"],
    )


def reset_vault(user_id: str | None = None) -> dict[str, int]:
    """Delete vault row and return the next vault_generation to use."""
    uid = user_id or vault_user_id()
    with _connect() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT vault_generation FROM public.portfolio_vault
                WHERE user_id = %s::uuid
                """,
                (uid,),
            )
            existing = cur.fetchone()
            next_gen = int(existing["vault_generation"]) + 1 if existing else 1
            cur.execute(
                "DELETE FROM public.portfolio_vault WHERE user_id = %s::uuid",
                (uid,),
            )
            conn.commit()
    return {"vault_generation": next_gen, "version": 0}
