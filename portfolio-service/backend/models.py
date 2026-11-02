import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum


class Base(DeclarativeBase):
    pass


class AccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class AssetType(str, enum.Enum):
    STOCK = "STOCK"
    MUTUAL_FUND = "MUTUAL_FUND"
    FIXED_DEPOSIT = "FIXED_DEPOSIT"
    BOND = "BOND"


class AssetStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class TransactionType(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str | None] = mapped_column(String(255))
    pan: Mapped[str | None] = mapped_column(String(20), unique=True)
    account_status: Mapped[AccountStatus] = mapped_column(SAEnum(AccountStatus, name="account_status"), default=AccountStatus.ACTIVE, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portfolio: Mapped["Portfolio | None"] = relationship(back_populates="user", uselist=False)


class Portfolio(TimestampMixin, Base):
    __tablename__ = "portfolios"
    portfolio_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"), unique=True, nullable=False)
    user: Mapped[User] = relationship(back_populates="portfolio")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="portfolio")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="portfolio")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("asset_type", "external_id", name="uq_assets_type_external_id"),)
    asset_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_type: Mapped[AssetType] = mapped_column(SAEnum(AssetType, name="asset_type"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    investment_class: Mapped[str] = mapped_column(String(20), default="EQUITY", nullable=False)
    status: Mapped[AssetStatus] = mapped_column(SAEnum(AssetStatus, name="asset_status"), default=AssetStatus.ACTIVE, nullable=False)
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="asset")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="asset")


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (Index("ix_transactions_portfolio_date", "portfolio_id", "transaction_date"), Index("ix_transactions_asset_date", "asset_id", "transaction_date"))
    transaction_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.portfolio_id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)
    transaction_type: Mapped[TransactionType] = mapped_column(SAEnum(TransactionType, name="transaction_type"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    transaction_amount: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_file: Mapped[str | None] = mapped_column(String(500))
    source_row: Mapped[int | None] = mapped_column()
    portfolio: Mapped[Portfolio] = relationship(back_populates="transactions")
    asset: Mapped[Asset] = relationship(back_populates="transactions")


class Holding(TimestampMixin, Base):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("portfolio_id", "asset_id", name="uq_holdings_portfolio_asset"),)
    holding_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.portfolio_id", ondelete="RESTRICT"), nullable=False)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    invested_amount: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    average_cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    portfolio: Mapped[Portfolio] = relationship(back_populates="holdings")
    asset: Mapped[Asset] = relationship(back_populates="holdings")
