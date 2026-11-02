import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from .dependencies import portfolio_session

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
from backend.models import Holding, Portfolio, Transaction, TransactionType  # noqa: E402
from backend.services import InsufficientHoldingsError  # noqa: E402

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


class TransactionRequest(BaseModel):
    asset_id: UUID
    transaction_type: TransactionType
    quantity: Decimal = Field(gt=0)
    price_per_unit: Decimal = Field(gt=0)
    transaction_date: date


def get_portfolio(session: Session, portfolio_id: UUID):
    portfolio = session.scalar(select(Portfolio).options(joinedload(Portfolio.user)).where(Portfolio.portfolio_id == portfolio_id))
    if portfolio is None or portfolio.user is None or portfolio.user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    return portfolio


@router.get("")
def list_portfolios(session: Session = Depends(portfolio_session)):
    rows = session.scalars(select(Portfolio).options(joinedload(Portfolio.user)).order_by(Portfolio.created_at)).all()
    return [{"portfolio_id": p.portfolio_id, "user_id": p.user_id, "user_name": p.user.full_name} for p in rows if p.user and p.user.deleted_at is None]


@router.get("/{portfolio_id}/holdings")
def holdings(portfolio_id: UUID, session: Session = Depends(portfolio_session)):
    get_portfolio(session, portfolio_id)
    rows = session.scalars(select(Holding).options(joinedload(Holding.asset)).where(Holding.portfolio_id == portfolio_id)).all()
    return [{"holding_id": h.holding_id, "asset_id": h.asset_id, "asset_name": h.asset.asset_name, "investment_class": h.asset.investment_class, "current_quantity": h.current_quantity, "invested_amount": h.invested_amount, "average_cost_per_unit": h.average_cost_per_unit} for h in rows]


@router.get("/{portfolio_id}/transactions")
def transactions(portfolio_id: UUID, from_date: date | None = None, to_date: date | None = None, transaction_type: TransactionType | None = None, session: Session = Depends(portfolio_session)):
    get_portfolio(session, portfolio_id)
    query = select(Transaction).options(joinedload(Transaction.asset)).where(Transaction.portfolio_id == portfolio_id)
    if from_date: query = query.where(Transaction.transaction_date >= from_date)
    if to_date: query = query.where(Transaction.transaction_date <= to_date)
    if transaction_type: query = query.where(Transaction.transaction_type == transaction_type)
    rows = session.scalars(query.order_by(Transaction.transaction_date.desc())).all()
    return [{"transaction_id": t.transaction_id, "asset_id": t.asset_id, "asset_name": t.asset.asset_name, "transaction_type": t.transaction_type, "quantity": t.quantity, "price_per_unit": t.price_per_unit, "transaction_amount": t.transaction_amount, "transaction_date": t.transaction_date} for t in rows]


@router.post("/{portfolio_id}/transactions", status_code=201)
def create_transaction(portfolio_id: UUID, request: TransactionRequest, session: Session = Depends(portfolio_session)):
    get_portfolio(session, portfolio_id)
    from backend.services import record_transaction
    try:
        transaction = session.execute  # keep the service boundary explicit
        # The async service is used by async application workers; this API currently
        # validates and applies the same weighted-average rules synchronously.
        from backend.models import Holding, Transaction as Tx
        holding = session.scalar(select(Holding).where(Holding.portfolio_id == portfolio_id, Holding.asset_id == request.asset_id).with_for_update())
        amount = request.quantity * request.price_per_unit
        if request.transaction_type is TransactionType.SELL:
            if holding is None or holding.current_quantity < request.quantity:
                raise InsufficientHoldingsError("insufficient holdings for redemption")
            remaining = holding.current_quantity - request.quantity
            holding.invested_amount -= holding.average_cost_per_unit * request.quantity
            if remaining == 0: session.delete(holding)
            else: holding.current_quantity = remaining
        elif holding is None:
            session.add(Holding(portfolio_id=portfolio_id, asset_id=request.asset_id, current_quantity=request.quantity, invested_amount=amount, average_cost_per_unit=amount / request.quantity))
        else:
            holding.current_quantity += request.quantity
            holding.invested_amount += amount
            holding.average_cost_per_unit = holding.invested_amount / holding.current_quantity
        tx = Tx(portfolio_id=portfolio_id, asset_id=request.asset_id, transaction_type=request.transaction_type, quantity=request.quantity, price_per_unit=request.price_per_unit, transaction_amount=amount, transaction_date=request.transaction_date)
        session.add(tx); session.commit(); session.refresh(tx)
        return {"transaction_id": tx.transaction_id, "transaction_amount": tx.transaction_amount}
    except InsufficientHoldingsError as exc:
        session.rollback(); raise HTTPException(status_code=409, detail=str(exc))
