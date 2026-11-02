"""Reference-data models owned by PostgreSQL."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class ReferenceBase(DeclarativeBase):
    pass

class MutualFundReference(ReferenceBase):
    __tablename__ = "mutual_fund_reference"
    __table_args__ = {"schema": "market_data"}
    scheme_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    scheme_code: Mapped[str | None] = mapped_column(String(50), unique=True)
    scheme_name: Mapped[str] = mapped_column(String(250), nullable=False)
    amc_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("market_data.amc_reference.amc_id"), nullable=False)
    subcategory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("market_data.mutual_fund_subcategories.subcategory_id"), nullable=False)
    benchmark_index_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("market_data.index_reference.index_id"))
    plan_type: Mapped[str] = mapped_column(String(20), nullable=False)
    option_type: Mapped[str] = mapped_column(String(30), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
