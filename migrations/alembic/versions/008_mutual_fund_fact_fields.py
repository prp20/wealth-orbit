"""Add canonical scheme metadata fields to mutual-fund enrichment snapshots."""
from alembic import op

revision = "008_mutual_fund_fact_fields"
down_revision = "007_groww_index_provider"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for column in ("fund_house", "scheme_type", "scheme_category"):
        op.execute(f"ALTER TABLE market_data.mutual_fund_enrichment ADD COLUMN IF NOT EXISTS {column} text")
    op.execute("ALTER TABLE market_data.mutual_fund_enrichment ADD COLUMN IF NOT EXISTS scheme_start_date date")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE market_data.mutual_fund_enrichment DROP COLUMN IF EXISTS scheme_start_date")
        for column in ("scheme_category", "scheme_type", "fund_house"):
            op.execute(f"ALTER TABLE market_data.mutual_fund_enrichment DROP COLUMN IF EXISTS {column}")
