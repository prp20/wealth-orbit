"""Drop persisted technical indicator cache; indicators are computed from OHLC."""
from alembic import op

revision = "013_drop_stock_tech"
down_revision = "012_holding_negative_weights"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS market_data.stock_technical_indicators")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    # Recreate the cache table shape for rollback only; writers no longer populate it.
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.stock_technical_indicators (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
      trading_date date NOT NULL,
      indicator_code varchar(20) NOT NULL,
      indicator_period integer NOT NULL DEFAULT 0,
      component varchar(20) NOT NULL DEFAULT 'VALUE',
      parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
      indicator_value numeric(24,8),
      calculation_status varchar(20) NOT NULL DEFAULT 'CURRENT'
        CHECK (calculation_status IN ('CURRENT', 'STALE', 'PENDING')),
      calculated_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (
        stock_id, trading_date, indicator_code, indicator_period, component, parameters
      ))"""
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_technical_lookup "
        "ON market_data.stock_technical_indicators(stock_id, indicator_code, trading_date)"
    )
