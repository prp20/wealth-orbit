"""Add fundamental_ratios JSONB on stock_daily_metrics (latest snapshot bag)."""

from alembic import op

revision = "013_fundamental_ratios"
down_revision = "012_holding_negative_weights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE market_data.stock_daily_metrics
          ADD COLUMN IF NOT EXISTS fundamental_ratios jsonb
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE market_data.stock_daily_metrics
          DROP COLUMN IF EXISTS fundamental_ratios
        """
    )
