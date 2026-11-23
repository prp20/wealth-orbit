from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID


def decimal_to_str(value: Decimal | str) -> str:
    if isinstance(value, str):
        return format(Decimal(value), "f")
    return format(value, "f")


@dataclass
class AssetSnapshot:
    asset_id: str
    asset_type: str
    external_id: str
    asset_name: str
    investment_class: str
    status: str


@dataclass
class TransactionSnapshot:
    transaction_id: str
    asset_id: str
    transaction_type: str
    quantity: str
    price_per_unit: str
    transaction_amount: str
    transaction_date: str
    source_file: str | None = None
    source_row: int | None = None


@dataclass
class HoldingSnapshot:
    holding_id: str
    asset_id: str
    current_quantity: str
    invested_amount: str
    average_cost_per_unit: str


@dataclass
class PortfolioSnapshot:
    schema_version: int
    exported_at: str
    portfolio_id: str
    assets: list[AssetSnapshot] = field(default_factory=list)
    transactions: list[TransactionSnapshot] = field(default_factory=list)
    holdings: list[HoldingSnapshot] = field(default_factory=list)


def snapshot_to_json(snapshot: PortfolioSnapshot) -> str:
    return json.dumps(asdict(snapshot), separators=(",", ":"), ensure_ascii=False)


def json_to_snapshot(data: str) -> PortfolioSnapshot:
    raw: dict[str, Any] = json.loads(data)
    if raw.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version: {raw.get('schema_version')}")
    return PortfolioSnapshot(
        schema_version=1,
        exported_at=raw["exported_at"],
        portfolio_id=raw["portfolio_id"],
        assets=[AssetSnapshot(**a) for a in raw.get("assets", [])],
        transactions=[TransactionSnapshot(**t) for t in raw.get("transactions", [])],
        holdings=[HoldingSnapshot(**h) for h in raw.get("holdings", [])],
    )


def _enum_str(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _uuid_str(value: UUID | str) -> str:
    return str(value)
