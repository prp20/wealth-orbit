"""Add calculation_version to stock_technical_indicators snapshots."""

from alembic import op

revision = "017_stock_tech_calc_version"
down_revision = "016_split_fundamentals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE market_data.stock_technical_indicators
        ADD COLUMN IF NOT EXISTS calculation_version varchar(30) NOT NULL DEFAULT 'tech_v1'
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        ALTER TABLE market_data.stock_technical_indicators
        DROP COLUMN IF EXISTS calculation_version
        """
    )