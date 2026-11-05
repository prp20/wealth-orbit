"""M03 P0 equity schema: identity fields, valuation columns, CA stubs, indexes."""
from alembic import op
import sqlalchemy as sa

revision = "010_m03_equity_research_p0"
down_revision = "009_mf_holdings_managers"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """ALTER TABLE market_data.stock_reference
           ADD COLUMN IF NOT EXISTS isin varchar(20),
           ADD COLUMN IF NOT EXISTS bse_code varchar(20),
           ADD COLUMN IF NOT EXISTS listing_date date,
           ADD COLUMN IF NOT EXISTS listing_status varchar(30),
           ADD COLUMN IF NOT EXISTS market_cap_class varchar(30)"""
    )

    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.stock_identity_events (
      event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
      event_date date NOT NULL,
      event_type varchar(40) NOT NULL,
      old_value text,
      new_value text,
      source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now()
    )"""
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_identity_events_stock "
        "ON market_data.stock_identity_events(stock_id, event_date DESC)"
    )

    op.execute(
        """ALTER TABLE market_data.stock_daily_prices
           ADD COLUMN IF NOT EXISTS adj_close numeric(18,6)"""
    )

    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.corporate_actions (
      action_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
      ex_date date NOT NULL,
      action_type varchar(40) NOT NULL,
      ratio numeric(18,8),
      source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(stock_id, ex_date, action_type)
    )"""
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_corporate_actions_stock "
        "ON market_data.corporate_actions(stock_id, ex_date DESC)"
    )

    op.execute(
        """ALTER TABLE market_data.stock_daily_metrics
           ADD COLUMN IF NOT EXISTS enterprise_value numeric(24,6),
           ADD COLUMN IF NOT EXISTS ebitda_ttm numeric(24,6),
           ADD COLUMN IF NOT EXISTS ev_ebitda numeric(18,8),
           ADD COLUMN IF NOT EXISTS ev_sales numeric(18,8),
           ADD COLUMN IF NOT EXISTS net_debt numeric(24,6),
           ADD COLUMN IF NOT EXISTS fcf_yield numeric(18,8),
           ADD COLUMN IF NOT EXISTS peg numeric(18,8)"""
    )

    op.execute(
        """ALTER TABLE market_data.stock_fundamental_values
           ADD COLUMN IF NOT EXISTS publication_date date,
           ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 1"""
    )

    for code, name, typ, unit in [
        ("EBITDA", "EBITDA", "PL", "INR"),
        ("NET_DEBT", "Net Debt", "BS", "INR"),
        ("FREE_CASH_FLOW", "Free Cash Flow", "CF", "INR"),
        ("SALES", "Sales", "PL", "INR"),
        ("ROE", "Return on Equity", "RATIOS", "PCT"),
        ("ROCE", "Return on Capital Employed", "RATIOS", "PCT"),
        ("DEBT_TO_EQUITY", "Debt to Equity", "RATIOS", "RATIO"),
        ("INTEREST_COVERAGE", "Interest Coverage", "RATIOS", "RATIO"),
        ("PAT_MARGIN", "PAT Margin", "RATIOS", "PCT"),
        ("REVENUE_GROWTH", "Revenue Growth", "RATIOS", "PCT"),
        ("EPS_GROWTH", "EPS Growth", "RATIOS", "PCT"),
    ]:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO market_data.fundamental_metric_reference"
                "(metric_code,metric_name,statement_type,unit) "
                "VALUES (:code,:name,:typ,:unit) ON CONFLICT(metric_code) DO NOTHING"
            ),
            {"code": code, "name": name, "typ": typ, "unit": unit},
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_reference_symbol ON market_data.stock_reference(trading_symbol)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_daily_prices_stock_date_desc "
        "ON market_data.stock_daily_prices(stock_id, trading_date DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_daily_metrics_stock_date_desc "
        "ON market_data.stock_daily_metrics(stock_id, metric_date DESC)"
    )
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_fundamentals_period")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_fundamentals_period "
        "ON market_data.stock_fundamental_values(stock_id, reporting_period, reporting_basis, period_end_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_jobs_entity_kind_queued "
        "ON market_data.sync_jobs(entity_type, entity_key, sync_type, queued_at DESC)"
    )


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS market_data.ix_sync_jobs_entity_kind_queued")
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_daily_metrics_stock_date_desc")
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_daily_prices_stock_date_desc")
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_reference_symbol")
    op.execute("DROP TABLE IF EXISTS market_data.corporate_actions")
    op.execute("DROP TABLE IF EXISTS market_data.stock_identity_events")
    op.execute(
        """ALTER TABLE market_data.stock_daily_metrics
           DROP COLUMN IF EXISTS enterprise_value,
           DROP COLUMN IF EXISTS ebitda_ttm,
           DROP COLUMN IF EXISTS ev_ebitda,
           DROP COLUMN IF EXISTS ev_sales,
           DROP COLUMN IF EXISTS net_debt,
           DROP COLUMN IF EXISTS fcf_yield,
           DROP COLUMN IF EXISTS peg"""
    )
    op.execute(
        """ALTER TABLE market_data.stock_fundamental_values
           DROP COLUMN IF EXISTS publication_date,
           DROP COLUMN IF EXISTS version"""
    )
    op.execute("ALTER TABLE market_data.stock_daily_prices DROP COLUMN IF EXISTS adj_close")
    op.execute(
        """ALTER TABLE market_data.stock_reference
           DROP COLUMN IF EXISTS isin,
           DROP COLUMN IF EXISTS bse_code,
           DROP COLUMN IF EXISTS listing_date,
           DROP COLUMN IF EXISTS listing_status,
           DROP COLUMN IF EXISTS market_cap_class"""
    )
