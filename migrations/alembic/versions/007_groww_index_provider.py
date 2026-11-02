"""Persist provider mappings for benchmark/index history."""
from alembic import op

revision = "007_groww_index_provider"
down_revision = "006_mutual_fund_analytics"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.index_provider_mappings (
      mapping_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), index_id uuid NOT NULL REFERENCES market_data.index_reference(index_id),
      provider varchar(30) NOT NULL, exchange varchar(20) NOT NULL, segment varchar(20) NOT NULL,
      trading_symbol varchar(255) NOT NULL, is_tri boolean NOT NULL DEFAULT false, is_active boolean NOT NULL DEFAULT true,
      last_successful_date date, source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(provider, trading_symbol))""")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS market_data.index_provider_mappings")
