"""Import a mutual-fund order-history workbook into the local portfolio DB."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openpyxl import load_workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.models import Asset, AssetStatus, AssetType, Base, Holding, Portfolio, Transaction, TransactionType, User


def money(value: object) -> Decimal:
    return Decimal(str(value).replace(",", "").strip())


def parse_date(value: object):
    return datetime.strptime(str(value).strip(), "%d %b %Y").date()


def read_rows(path: Path):
    sheet = load_workbook(path, read_only=True, data_only=True).active
    header_row = next(i for i, row in enumerate(sheet.iter_rows(values_only=True), 1) if row[:6] == ("Scheme Name", "Transaction Type", "Units", "NAV", "Amount", "Date"))
    rows = []
    for row in sheet.iter_rows(min_row=header_row + 1, values_only=True):
        if not row[0]:
            continue
        rows.append({"source_row": header_row + len(rows) + 1, "name": str(row[0]).strip(), "type": str(row[1]).strip().upper(), "quantity": money(row[2]), "price": money(row[3]), "amount": money(row[4]), "date": parse_date(row[5])})
    return rows


def investment_class(name: str) -> str:
    lowered = name.lower()
    return "DEBT" if any(term in lowered for term in ("short term", "ultra short", "liquid", "money market", "corporate bond", "gilt")) else "EQUITY"


def import_file(path: Path, database_url: str, mode: str = "append", source_name: str | None = None) -> int:
    rows = read_rows(path)
    source_name = source_name or path.name
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        user = session.scalar(select(User).order_by(User.created_at).limit(1))
        if user is None:
            user = User(account_status="ACTIVE", full_name="Pete Ravidas Prasad", pan="CSFPP1692E")
            session.add(user)
            session.flush()
        portfolio = user.portfolio
        if portfolio is None:
            portfolio = Portfolio(user_id=user.user_id)
            session.add(portfolio)
            session.flush()
        if mode == "update":
            session.query(Transaction).filter(Transaction.source_file == source_name).delete(synchronize_session=False)
            session.query(Holding).filter(Holding.portfolio_id == portfolio.portfolio_id).delete(synchronize_session=False)
        assets: dict[str, Asset] = {asset.asset_name: asset for asset in session.scalars(select(Asset)).all()}
        existing_rows = set(session.execute(select(Transaction.source_row).where(Transaction.source_file == source_name)).scalars())
        for row in sorted(rows, key=lambda item: item["date"]):
            if mode == "append" and row["source_row"] in existing_rows:
                continue
            asset = assets.get(row["name"])
            if asset is None:
                asset = Asset(asset_type=AssetType.MUTUAL_FUND, external_id=row["name"], asset_name=row["name"], investment_class=investment_class(row["name"]), status=AssetStatus.ACTIVE)
                assets[row["name"]] = asset
                session.add(asset)
                session.flush()
            else:
                asset.investment_class = investment_class(row["name"])
            holding = session.scalar(select(Holding).where(Holding.portfolio_id == portfolio.portfolio_id, Holding.asset_id == asset.asset_id).with_for_update())
            tx_type = TransactionType.BUY if row["type"] in {"BUY", "PURCHASE"} else TransactionType.SELL
            quantity, amount = row["quantity"], row["amount"]
            if tx_type is TransactionType.SELL:
                if holding is None or holding.current_quantity < quantity:
                    # The export can contain redemptions for units acquired before
                    # the report window. Seed that opening position so every
                    # source row is retained without creating negative holdings.
                    if holding is None:
                        opening = Holding(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, current_quantity=quantity, invested_amount=amount, average_cost_per_unit=amount / quantity)
                        session.add(opening)
                        session.flush()
                        holding = opening
                    else:
                        shortfall = quantity - holding.current_quantity
                        holding.invested_amount += shortfall * (amount / quantity)
                        holding.current_quantity = quantity
                        holding.average_cost_per_unit = holding.invested_amount / holding.current_quantity
                    session.add(Transaction(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, transaction_type=TransactionType.BUY, quantity=quantity, price_per_unit=row["price"], transaction_amount=amount, transaction_date=row["date"]))
                remaining = holding.current_quantity - quantity
                holding.invested_amount -= holding.average_cost_per_unit * quantity
                if remaining == 0:
                    session.delete(holding)
                else:
                    holding.current_quantity = remaining
            elif holding is None:
                session.add(Holding(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, current_quantity=quantity, invested_amount=amount, average_cost_per_unit=amount / quantity))
            else:
                holding.current_quantity += quantity
                holding.invested_amount += amount
                holding.average_cost_per_unit = holding.invested_amount / holding.current_quantity
            session.add(Transaction(portfolio_id=portfolio.portfolio_id, asset_id=asset.asset_id, transaction_type=tx_type, quantity=quantity, price_per_unit=row["price"], transaction_amount=amount, transaction_date=row["date"], source_file=source_name, source_row=row["source_row"]))
        session.commit()
        print(f"Imported {len(rows)} transactions, {len(assets)} assets, portfolio {portfolio.portfolio_id}")
        return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--database-url", default="sqlite:///./portfolio-service/portfolio.db")
    parser.add_argument("--mode", choices=["append", "update"], default="append")
    args = parser.parse_args()
    import_file(args.workbook, args.database_url, args.mode)
