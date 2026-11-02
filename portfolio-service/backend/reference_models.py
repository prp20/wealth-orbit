"""Reference-data models owned by PostgreSQL."""
from datetime import datetime
from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class ReferenceBase(DeclarativeBase):
    pass

class MutualFundReference(ReferenceBase):
    __tablename__ = "mutual_fund_references"
    scheme_code: Mapped[str] = mapped_column(String(100), primary_key=True)
    scheme_name: Mapped[str] = mapped_column(String(500), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(50), unique=True)
    fund_house: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
