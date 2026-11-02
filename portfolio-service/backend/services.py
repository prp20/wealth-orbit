from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Asset, Holding, Portfolio, Transaction, TransactionType


class InsufficientHoldingsError(ValueError):
    pass


async def record_transaction(
    session: AsyncSession, *, portfolio_id, asset_id, transaction_type: TransactionType,
    quantity: Decimal, price_per_unit: Decimal, transaction_date: date,
) -> Transaction:
    if quantity <= 0 or price_per_unit <= 0:
        raise ValueError("quantity and price_per_unit must be positive")
    amount = quantity * price_per_unit
    async with session.begin():
        await session.execute(select(Portfolio).where(Portfolio.portfolio_id == portfolio_id).with_for_update())
        await session.execute(select(Asset).where(Asset.asset_id == asset_id))
        result = await session.execute(select(Holding).where(Holding.portfolio_id == portfolio_id, Holding.asset_id == asset_id).with_for_update())
        holding = result.scalar_one_or_none()
        if transaction_type is TransactionType.SELL:
            if holding is None or holding.current_quantity < quantity:
                raise InsufficientHoldingsError("insufficient holdings for redemption")
            new_quantity = holding.current_quantity - quantity
            holding.invested_amount -= holding.average_cost_per_unit * quantity
            if new_quantity == 0:
                await session.delete(holding)
            else:
                holding.current_quantity = new_quantity
        else:
            if holding is None:
                holding = Holding(portfolio_id=portfolio_id, asset_id=asset_id, current_quantity=quantity, invested_amount=amount, average_cost_per_unit=amount / quantity)
                session.add(holding)
            else:
                holding.current_quantity += quantity
                holding.invested_amount += amount
                holding.average_cost_per_unit = holding.invested_amount / holding.current_quantity
        transaction = Transaction(portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=transaction_type, quantity=quantity, price_per_unit=price_per_unit, transaction_amount=amount, transaction_date=transaction_date)
        session.add(transaction)
    return transaction
