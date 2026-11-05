from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import COOKIE, MAX_AGE_SECONDS, hash_password, read_session, sign_session, verify_password
from .dependencies import portfolio_session
from .portfolio_backend import Portfolio, User

router = APIRouter(prefix="/auth", tags=["auth"])


class AccountBody(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=200)


def _public(user: User, portfolio, signed_in: bool = True) -> dict:
    return {
        "signed_in": signed_in,
        "full_name": user.full_name if signed_in else None,
        "portfolio_id": portfolio.portfolio_id if signed_in and portfolio else None,
    }


def _anonymous() -> dict:
    return {"signed_in": False, "full_name": None, "portfolio_id": None}


def _named_user(session: Session, full_name: str) -> User | None:
    name = full_name.strip()
    return session.scalar(
        select(User).where(User.deleted_at.is_(None), func.lower(User.full_name) == name.lower())
    )


def _attach(response: Response, user_id) -> None:
    response.set_cookie(
        COOKIE,
        sign_session(str(user_id)),
        max_age=MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )


@router.get("/status")
def auth_status(session: Session = Depends(portfolio_session)):
    users = session.scalars(select(User).where(User.deleted_at.is_(None))).all()
    return {"password_set": any(user.password_hash for user in users)}


@router.get("/me")
def auth_me(request: Request, session: Session = Depends(portfolio_session)):
    user_id = read_session(request.cookies.get(COOKIE))
    if not user_id:
        return _anonymous()
    user = session.get(User, UUID(user_id))
    if user is None or user.deleted_at is not None:
        return _anonymous()
    portfolio = session.scalar(select(Portfolio).where(Portfolio.user_id == user.user_id))
    return _public(user, portfolio)


@router.post("/signup")
def auth_signup(body: AccountBody, response: Response, session: Session = Depends(portfolio_session)):
    name = body.full_name.strip()
    if _named_user(session, name):
        raise HTTPException(status_code=409, detail="An account with that name already exists. Sign in instead.")
    user = User(full_name=name, password_hash=hash_password(body.password))
    session.add(user)
    session.flush()
    portfolio = Portfolio(user_id=user.user_id)
    session.add(portfolio)
    session.commit()
    _attach(response, user.user_id)
    return _public(user, portfolio)


@router.post("/login")
def auth_login(body: AccountBody, response: Response, session: Session = Depends(portfolio_session)):
    user = _named_user(session, body.full_name)
    if user is None or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="That name or password is not right.")
    portfolio = session.scalar(select(Portfolio).where(Portfolio.user_id == user.user_id))
    _attach(response, user.user_id)
    return _public(user, portfolio)


@router.post("/logout")
def auth_logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}
