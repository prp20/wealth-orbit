"""Store the seed business summary and clear forward PEG values."""
from alembic import op

revision = "011_stock_business_summary"
down_revision = "010_m03_equity_research_p0"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """ALTER TABLE market_data.stock_reference
           ADD COLUMN IF NOT EXISTS business_summary text"""
    )
    op.execute("UPDATE market_data.stock_daily_metrics SET peg = NULL WHERE peg IS NOT NULL")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE market_data.stock_reference DROP COLUMN IF EXISTS business_summary")
