"""Local password and signed session cookie for the SQLite account."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from .dependencies import portfolio_session, portfolio_url
from .portfolio_backend import Portfolio, User

COOKIE = "wealth_orbit_session"
MAX_AGE_SECONDS = 60 * 60 * 24 * 30
_PBKDF2_ROUNDS = 200_000


def ensure_password_column() -> None:
    from sqlalchemy import create_engine

    engine = create_engine(portfolio_url())
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return
    names = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" in names:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ROUNDS).hex()
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _algo, rounds, salt, digest = stored.split("$", 3)
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check, digest)


def _secret() -> bytes:
    value = os.environ.get("SESSION_SECRET", "").strip()
    if not value:
        raise HTTPException(status_code=500, detail="SESSION_SECRET is not set")
    return value.encode()


def sign_session(user_id: str, now: int | None = None) -> str:
    issued = int(time.time()) if now is None else now
    payload = f"{user_id}.{issued + MAX_AGE_SECONDS}"
    signature = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def read_session(token: str | None, now: int | None = None) -> str | None:
    if not token:
        return None
    try:
        user_id, expiry, signature = token.split(".", 2)
        payload = f"{user_id}.{expiry}"
        expected = hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        if int(expiry) < (int(time.time()) if now is None else now):
            return None
        UUID(user_id)
    except (ValueError, HTTPException):
        return None
    return user_id


def local_account(session: Session) -> tuple[User, Portfolio | None]:
    user = session.scalar(select(User).where(User.deleted_at.is_(None)).order_by(User.created_at).limit(1))
    if user is None:
        raise HTTPException(status_code=404, detail="No local account is set up")
    portfolio = session.scalar(select(Portfolio).where(Portfolio.user_id == user.user_id))
    return user, portfolio


def current_user(request: Request, session: Session = Depends(portfolio_session)) -> User:
    user_id = read_session(request.cookies.get(COOKIE))
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in required")
    user = session.get(User, UUID(user_id))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user
