"""Allow negative portfolio weights such as payables."""
from alembic import op

revision = "012_holding_negative_weights"
down_revision = "011_stock_business_summary"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE market_data.mutual_fund_portfolio_holdings "
        "DROP CONSTRAINT IF EXISTS mutual_fund_portfolio_holdings_weight_pct_check"
    )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        "ALTER TABLE market_data.mutual_fund_portfolio_holdings "
        "ADD CONSTRAINT mutual_fund_portfolio_holdings_weight_pct_check CHECK (weight_pct >= 0)"
    )
