from __future__ import annotations

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.models import Asset, AssetType, Base, Portfolio, TransactionType, User
from backend.services import record_transaction
from backend.vault.crypto import decrypt_snapshot, encrypt_snapshot
from backend.vault.schema import json_to_snapshot, snapshot_to_json
from backend.vault.sqlite_export import export_portfolio_from_sqlite


@pytest.fixture
async def session_with_one_buy():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        user = User()
        db.add(user)
        await db.flush()
        portfolio = Portfolio(user_id=user.user_id)
        asset = Asset(
            asset_type=AssetType.MUTUAL_FUND,
            external_id="MF-1",
            asset_name="Fund",
        )
        db.add_all([portfolio, asset])
        await db.commit()
        await record_transaction(
            db,
            portfolio_id=portfolio.portfolio_id,
            asset_id=asset.asset_id,
            transaction_type=TransactionType.BUY,
            quantity=Decimal("100"),
            price_per_unit=Decimal("10.5"),
            transaction_date=date(2026, 1, 15),
        )
        yield db, portfolio.portfolio_id, str(user.user_id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_export_includes_holding_decimal_as_string(session_with_one_buy):
    db, portfolio_id, _user_id = session_with_one_buy
    snap = await export_portfolio_from_sqlite(db, portfolio_id)
    raw = snapshot_to_json(snap)
    parsed = json.loads(raw)
    assert parsed["schema_version"] == 1
    assert len(snap.holdings) == 1
    assert isinstance(snap.holdings[0].current_quantity, str)
    assert snap.holdings[0].current_quantity == "100.000000000000"
    assert snap.holdings[0].average_cost_per_unit == "10.500000000000"
    assert len(snap.transactions) == 1
    assert snap.transactions[0].transaction_date == "2026-01-15"
    round_trip = json_to_snapshot(raw)
    assert round_trip.portfolio_id == snap.portfolio_id
    assert round_trip.holdings[0].current_quantity == snap.holdings[0].current_quantity


@pytest.mark.asyncio
async def test_export_encrypt_round_trip(session_with_one_buy):
    db, portfolio_id, user_id = session_with_one_buy
    snap = await export_portfolio_from_sqlite(db, portfolio_id)
    plain = snapshot_to_json(snap)
    ct = encrypt_snapshot(
        plain, secret="unit-test-secret", user_id=user_id, vault_generation=1
    )
    restored = decrypt_snapshot(
        ct, secret="unit-test-secret", user_id=user_id, vault_generation=1
    )
    assert json_to_snapshot(restored).holdings[0].current_quantity == "100.000000000000"
