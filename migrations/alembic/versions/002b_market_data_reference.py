"""Create the market reference tables that later migrations extend.

These tables lived in the original database and were not created by Alembic.
A fresh setup reached migration 003 and failed because stock_daily_metrics
references stock_reference. This revision sits before that migration so a
database that stopped there creates the missing tables on the next upgrade.

Downgrade does nothing. Databases that already had these tables never ran
this upgrade, and dropping the tables would delete their market data.
"""
from alembic import op

revision = "002b_market_data_reference"
down_revision = "002_identity_and_import_tracking"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("CREATE SCHEMA IF NOT EXISTS market_data")
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.data_sources (
      source_id uuid PRIMARY KEY,
      source_name varchar(150) NOT NULL UNIQUE,
      status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'INACTIVE')),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.sector_reference (
      sector_id uuid PRIMARY KEY,
      sector_name varchar(150) NOT NULL UNIQUE,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.industry_reference (
      industry_id uuid PRIMARY KEY,
      sector_id uuid NOT NULL REFERENCES market_data.sector_reference(sector_id),
      industry_name varchar(150) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_industry_sector_id UNIQUE (sector_id, industry_id),
      CONSTRAINT uq_industry_sector_name UNIQUE (sector_id, industry_name))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.stock_reference (
      stock_id uuid PRIMARY KEY,
      trading_symbol varchar(50) NOT NULL,
      exchange varchar(20) NOT NULL,
      isin varchar(12),
      company_name varchar(250) NOT NULL,
      sector_id uuid REFERENCES market_data.sector_reference(sector_id),
      industry_id uuid,
      is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_stock_exchange_symbol UNIQUE (exchange, trading_symbol),
      CONSTRAINT uq_stock_isin UNIQUE (isin),
      FOREIGN KEY (sector_id, industry_id)
        REFERENCES market_data.industry_reference(sector_id, industry_id),
      CHECK (industry_id IS NULL OR sector_id IS NOT NULL))"""
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_stock_sector ON market_data.stock_reference(sector_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stock_industry ON market_data.stock_reference(industry_id)")
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.stock_daily_prices (
      stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
      trading_date date NOT NULL,
      open numeric(20,6) NOT NULL,
      high numeric(20,6) NOT NULL,
      low numeric(20,6) NOT NULL,
      close numeric(20,6) NOT NULL,
      volume bigint NOT NULL,
      source_id uuid NOT NULL REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (stock_id, trading_date),
      CHECK (open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0
             AND high >= open AND high >= close AND high >= low
             AND low <= open AND low <= close))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.index_reference (
      index_id uuid PRIMARY KEY,
      index_name varchar(200) NOT NULL,
      index_code varchar(100) UNIQUE,
      is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.amc_reference (
      amc_id uuid PRIMARY KEY,
      amc_name varchar(200) NOT NULL UNIQUE,
      amc_code varchar(50) UNIQUE,
      is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_categories (
      category_id uuid PRIMARY KEY,
      category_name varchar(100) NOT NULL UNIQUE,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_subcategories (
      subcategory_id uuid PRIMARY KEY,
      category_id uuid NOT NULL REFERENCES market_data.mutual_fund_categories(category_id),
      subcategory_name varchar(150) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT uq_subcategory_name UNIQUE (category_id, subcategory_name))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_reference (
      scheme_id uuid PRIMARY KEY,
      scheme_code varchar(50) UNIQUE,
      scheme_name varchar(250) NOT NULL,
      amc_id uuid NOT NULL REFERENCES market_data.amc_reference(amc_id),
      subcategory_id uuid NOT NULL REFERENCES market_data.mutual_fund_subcategories(subcategory_id),
      benchmark_index_id uuid REFERENCES market_data.index_reference(index_id),
      plan_type varchar(20) NOT NULL CHECK (plan_type IN ('DIRECT', 'REGULAR')),
      option_type varchar(30) NOT NULL CHECK (option_type IN ('GROWTH', 'IDCW')),
      is_active boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_scheme_amc ON market_data.mutual_fund_reference(amc_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_scheme_benchmark ON market_data.mutual_fund_reference(benchmark_index_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_scheme_subcategory ON market_data.mutual_fund_reference(subcategory_id)")
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_nav_history (
      scheme_id uuid NOT NULL REFERENCES market_data.mutual_fund_reference(scheme_id),
      nav_date date NOT NULL,
      nav numeric(20,6) NOT NULL CHECK (nav > 0),
      source_id uuid NOT NULL REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (scheme_id, nav_date))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.data_source_priorities (
      source_id uuid NOT NULL REFERENCES market_data.data_sources(source_id),
      asset_type varchar(20) NOT NULL CHECK (asset_type IN ('STOCK', 'MUTUAL_FUND', 'INDEX')),
      priority integer NOT NULL CHECK (priority > 0),
      is_enabled boolean NOT NULL DEFAULT true,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (source_id, asset_type),
      UNIQUE (asset_type, priority))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.ingestion_runs (
      run_id uuid PRIMARY KEY,
      source_id uuid NOT NULL REFERENCES market_data.data_sources(source_id),
      asset_type varchar(20) NOT NULL CHECK (asset_type IN ('STOCK', 'MUTUAL_FUND', 'INDEX')),
      started_at timestamptz NOT NULL DEFAULT now(),
      completed_at timestamptz,
      status varchar(30) NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'SUCCESS', 'PARTIAL_SUCCESS', 'FAILED')),
      records_inserted integer NOT NULL DEFAULT 0,
      records_updated integer NOT NULL DEFAULT 0,
      records_failed integer NOT NULL DEFAULT 0,
      created_at timestamptz NOT NULL DEFAULT now(),
      CHECK (records_inserted >= 0 AND records_updated >= 0 AND records_failed >= 0))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.ingestion_errors (
      error_id uuid PRIMARY KEY,
      run_id uuid NOT NULL REFERENCES market_data.ingestion_runs(run_id),
      asset_type varchar(20) NOT NULL,
      stock_id uuid REFERENCES market_data.stock_reference(stock_id),
      scheme_id uuid REFERENCES market_data.mutual_fund_reference(scheme_id),
      index_id uuid REFERENCES market_data.index_reference(index_id),
      observation_date date NOT NULL,
      error_message text,
      retry_count integer NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
      next_retry_at timestamptz,
      status varchar(30) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'RETRYING', 'RESOLVED', 'PERMANENT_FAILURE')),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      CHECK (
        (asset_type = 'STOCK' AND stock_id IS NOT NULL AND scheme_id IS NULL AND index_id IS NULL)
        OR (asset_type = 'MUTUAL_FUND' AND stock_id IS NULL AND scheme_id IS NOT NULL AND index_id IS NULL)
        OR (asset_type = 'INDEX' AND stock_id IS NULL AND scheme_id IS NULL AND index_id IS NOT NULL)
      ))"""
    )


def downgrade():
    return
