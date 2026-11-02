from datetime import date
from decimal import Decimal
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portfolio-service"))

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models import Asset, AssetType, Base, Portfolio, TransactionType, User
from backend.services import InsufficientHoldingsError, record_transaction


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User()
        db.add(user)
        await db.flush()
        portfolio = Portfolio(user_id=user.user_id)
        asset = Asset(asset_type=AssetType.MUTUAL_FUND, external_id="MF-1", asset_name="Fund")
        db.add_all([portfolio, asset])
        await db.commit()
        yield db, portfolio.portfolio_id, asset.asset_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_weighted_average_and_partial_redemption(session):
    db, portfolio_id, asset_id = session
    await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.BUY, quantity=Decimal("100"), price_per_unit=Decimal("100"), transaction_date=date.today())
    await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.BUY, quantity=Decimal("100"), price_per_unit=Decimal("120"), transaction_date=date.today())
    await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.SELL, quantity=Decimal("100"), price_per_unit=Decimal("130"), transaction_date=date.today())
    result = await db.execute(__import__("sqlalchemy").select(__import__("app.models", fromlist=["Holding"]).Holding))
    holding = result.scalar_one()
    assert holding.current_quantity == Decimal("100")
    assert holding.invested_amount == Decimal("11000")
    assert holding.average_cost_per_unit == Decimal("110")


@pytest.mark.asyncio
async def test_full_redemption_deletes_holding(session):
    db, portfolio_id, asset_id = session
    await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.BUY, quantity=Decimal("10"), price_per_unit=Decimal("50"), transaction_date=date.today())
    await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.SELL, quantity=Decimal("10"), price_per_unit=Decimal("55"), transaction_date=date.today())
    from backend.models import Holding
    assert (await db.execute(__import__("sqlalchemy").select(Holding))).scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_sell_cannot_oversell(session):
    db, portfolio_id, asset_id = session
    with pytest.raises(InsufficientHoldingsError):
        await record_transaction(db, portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=TransactionType.SELL, quantity=Decimal("1"), price_per_unit=Decimal("1"), transaction_date=date.today())
