"""stock fundamentals, shareholding, and technical indicator cache"""
from alembic import op
import sqlalchemy as sa

revision = "003_stock_fundamentals_technical"
down_revision = "002_identity_and_import_tracking"
branch_labels = None
depends_on = None

def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE SCHEMA IF NOT EXISTS market_data""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.stock_daily_metrics (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id), metric_date date NOT NULL,
      market_cap numeric(24,6), stock_pe numeric(18,8), price_to_book numeric(18,8), dividend_yield numeric(18,8),
      book_value numeric(24,8), roce numeric(18,8), roe numeric(18,8), calculation_method varchar(20) NOT NULL DEFAULT 'PROVIDER',
      source_id uuid REFERENCES market_data.data_sources(source_id), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(stock_id, metric_date), CHECK(calculation_method IN ('PROVIDER','CALCULATED')) )""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.fundamental_metric_reference (
      metric_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), metric_code varchar(100) NOT NULL UNIQUE, metric_name varchar(255) NOT NULL,
      statement_type varchar(20) NOT NULL CHECK(statement_type IN ('PL','BS','CF','RATIOS')), unit varchar(50), description text,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.stock_fundamental_values (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id), metric_id uuid NOT NULL REFERENCES market_data.fundamental_metric_reference(metric_id),
      reporting_period varchar(20) NOT NULL CHECK(reporting_period IN ('QUARTERLY','ANNUAL')), period_start_date date, period_end_date date NOT NULL,
      reporting_basis varchar(20) NOT NULL CHECK(reporting_basis IN ('CONSOLIDATED','STANDALONE')), metric_value numeric(30,10), source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(stock_id, metric_id, reporting_period, reporting_basis, period_end_date))""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.stock_shareholding_history (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id), period_end_date date NOT NULL,
      promoter_pct numeric(8,4) CHECK(promoter_pct BETWEEN 0 AND 100), fii_pct numeric(8,4) CHECK(fii_pct BETWEEN 0 AND 100),
      dii_pct numeric(8,4) CHECK(dii_pct BETWEEN 0 AND 100), government_pct numeric(8,4) CHECK(government_pct BETWEEN 0 AND 100),
      public_pct numeric(8,4) CHECK(public_pct BETWEEN 0 AND 100), shareholder_count bigint, source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(stock_id, period_end_date))""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.stock_technical_indicators (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id), trading_date date NOT NULL, indicator_code varchar(20) NOT NULL,
      indicator_period integer NOT NULL DEFAULT 0, component varchar(20) NOT NULL DEFAULT 'VALUE', parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
      indicator_value numeric(24,8), calculation_status varchar(20) NOT NULL DEFAULT 'CURRENT' CHECK(calculation_status IN ('CURRENT','STALE','PENDING')),
      calculated_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(stock_id, trading_date, indicator_code, indicator_period, component, parameters))""")
    seed = [("REVENUE","Revenue","PL","INR"),("NET_PROFIT","Net Profit","PL","INR"),("EPS","Earnings Per Share","RATIOS","INR"),("TOTAL_ASSETS","Total Assets","BS","INR"),("TOTAL_DEBT","Total Debt","BS","INR"),("OPERATING_CASH_FLOW","Operating Cash Flow","CF","INR")]
    for code,name,typ,unit in seed:
        op.get_bind().execute(sa.text("INSERT INTO market_data.fundamental_metric_reference(metric_code,metric_name,statement_type,unit) VALUES (:code,:name,:typ,:unit) ON CONFLICT(metric_code) DO NOTHING"), {"code": code, "name": name, "typ": typ, "unit": unit})
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_metrics_date ON market_data.stock_daily_metrics(stock_id, metric_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_fundamentals_period ON market_data.stock_fundamental_values(stock_id, reporting_period, period_end_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_technical_lookup ON market_data.stock_technical_indicators(stock_id, indicator_code, trading_date)")

def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in ("stock_technical_indicators","stock_shareholding_history","stock_fundamental_values","fundamental_metric_reference","stock_daily_metrics"):
        op.execute(f"DROP TABLE IF EXISTS market_data.{table}")
