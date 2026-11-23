from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Asset, Holding, Portfolio, Transaction
from backend.vault.schema import (
    AssetSnapshot,
    HoldingSnapshot,
    PortfolioSnapshot,
    TransactionSnapshot,
    _enum_str,
    _uuid_str,
    decimal_to_str,
)


async def export_portfolio_from_sqlite(
    session: AsyncSession, portfolio_id: UUID
) -> PortfolioSnapshot:
    result = await session.execute(
        select(Portfolio)
        .where(Portfolio.portfolio_id == portfolio_id)
        .options(
            selectinload(Portfolio.transactions).selectinload(Transaction.asset),
            selectinload(Portfolio.holdings).selectinload(Holding.asset),
        )
    )
    portfolio = result.scalar_one()

    asset_by_id: dict[UUID, Asset] = {}
    for tx in portfolio.transactions:
        asset_by_id[tx.asset_id] = tx.asset
    for holding in portfolio.holdings:
        asset_by_id[holding.asset_id] = holding.asset

    assets = [
        AssetSnapshot(
            asset_id=_uuid_str(asset.asset_id),
            asset_type=_enum_str(asset.asset_type),
            external_id=asset.external_id,
            asset_name=asset.asset_name,
            investment_class=asset.investment_class,
            status=_enum_str(asset.status),
        )
        for asset in sorted(asset_by_id.values(), key=lambda a: str(a.asset_id))
    ]

    transactions = [
        TransactionSnapshot(
            transaction_id=_uuid_str(tx.transaction_id),
            asset_id=_uuid_str(tx.asset_id),
            transaction_type=_enum_str(tx.transaction_type),
            quantity=decimal_to_str(tx.quantity),
            price_per_unit=decimal_to_str(tx.price_per_unit),
            transaction_amount=decimal_to_str(tx.transaction_amount),
            transaction_date=tx.transaction_date.isoformat(),
            source_file=tx.source_file,
            source_row=tx.source_row,
        )
        for tx in sorted(
            portfolio.transactions,
            key=lambda t: (t.transaction_date.isoformat(), str(t.transaction_id)),
        )
    ]

    holdings = [
        HoldingSnapshot(
            holding_id=_uuid_str(h.holding_id),
            asset_id=_uuid_str(h.asset_id),
            current_quantity=decimal_to_str(h.current_quantity),
            invested_amount=decimal_to_str(h.invested_amount),
            average_cost_per_unit=decimal_to_str(h.average_cost_per_unit),
        )
        for h in sorted(portfolio.holdings, key=lambda h: str(h.holding_id))
    ]

    return PortfolioSnapshot(
        schema_version=1,
        exported_at=datetime.now(timezone.utc).isoformat(),
        portfolio_id=_uuid_str(portfolio.portfolio_id),
        assets=assets,
        transactions=transactions,
        holdings=holdings,
    )
