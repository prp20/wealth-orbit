"""Add fundamental_ratios JSONB on stock_daily_metrics (latest snapshot bag)."""

from alembic import op

revision = "015_fundamental_ratios"
down_revision = "014_stock_tech_latest"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # market_data lives on Supabase Postgres only; local SQLite is the ledger.
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE market_data.stock_daily_metrics
          ADD COLUMN IF NOT EXISTS fundamental_ratios jsonb
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE market_data.stock_daily_metrics
          DROP COLUMN IF EXISTS fundamental_ratios
        """
    )
