"""initial portfolio schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        for name, values in [("account_status", ["ACTIVE", "SUSPENDED", "CLOSED"]), ("asset_type", ["STOCK", "MUTUAL_FUND", "FIXED_DEPOSIT", "BOND"]), ("asset_status", ["ACTIVE", "INACTIVE"]), ("transaction_type", ["BUY", "SELL"])]:
            postgresql.ENUM(*values, name=name).create(bind)
    uuid = postgresql.UUID(as_uuid=True)
    if not is_postgres: uuid = sa.String(36)
    enum = lambda name: postgresql.ENUM(name=name, create_type=False) if is_postgres else sa.String(30)
    op.create_table("users", sa.Column("user_id", uuid, primary_key=True), sa.Column("account_status", enum("account_status"), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("portfolios", sa.Column("portfolio_id", uuid, primary_key=True), sa.Column("user_id", uuid, sa.ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("assets", sa.Column("asset_id", uuid, primary_key=True), sa.Column("asset_type", enum("asset_type"), nullable=False), sa.Column("external_id", sa.String(255), nullable=False), sa.Column("asset_name", sa.String(255), nullable=False), sa.Column("status", enum("asset_status"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("asset_type", "external_id", name="uq_assets_type_external_id"))
    op.create_table("transactions", sa.Column("transaction_id", uuid, primary_key=True), sa.Column("portfolio_id", uuid, sa.ForeignKey("portfolios.portfolio_id", ondelete="RESTRICT"), nullable=False), sa.Column("asset_id", uuid, sa.ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False), sa.Column("transaction_type", enum("transaction_type"), nullable=False), sa.Column("quantity", sa.Numeric(30, 12), nullable=False), sa.Column("price_per_unit", sa.Numeric(30, 12), nullable=False), sa.Column("transaction_amount", sa.Numeric(30, 12), nullable=False), sa.Column("transaction_date", sa.Date(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_transactions_portfolio_date", "transactions", ["portfolio_id", "transaction_date"])
    op.create_index("ix_transactions_asset_date", "transactions", ["asset_id", "transaction_date"])
    op.create_table("holdings", sa.Column("holding_id", uuid, primary_key=True), sa.Column("portfolio_id", uuid, sa.ForeignKey("portfolios.portfolio_id", ondelete="RESTRICT"), nullable=False), sa.Column("asset_id", uuid, sa.ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False), sa.Column("current_quantity", sa.Numeric(30, 12), nullable=False), sa.Column("invested_amount", sa.Numeric(30, 12), nullable=False), sa.Column("average_cost_per_unit", sa.Numeric(30, 12), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("portfolio_id", "asset_id", name="uq_holdings_portfolio_asset"))

def downgrade():
    for table in ["holdings", "transactions", "assets", "portfolios", "users"]: op.drop_table(table)
    if op.get_bind().dialect.name == "postgresql":
        for name in ["transaction_type", "asset_status", "asset_type", "account_status"]: postgresql.ENUM(name=name).drop(op.get_bind())
