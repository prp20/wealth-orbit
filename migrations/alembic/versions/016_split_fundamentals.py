"""Split stock_fundamental_values into annual and quarterly tables."""

from alembic import op

revision = "016_split_fundamentals"
down_revision = "015_fundamental_ratios"
branch_labels = None
depends_on = None

_ANNUAL_DDL = """
CREATE TABLE IF NOT EXISTS market_data.stock_annual_fundamental_values (
  stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
  metric_id uuid NOT NULL REFERENCES market_data.fundamental_metric_reference(metric_id),
  period_start_date date,
  period_end_date date NOT NULL,
  reporting_basis varchar(20) NOT NULL CHECK (reporting_basis IN ('CONSOLIDATED', 'STANDALONE')),
  metric_value numeric(30, 10),
  source_id uuid REFERENCES market_data.data_sources(source_id),
  publication_date date,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (stock_id, metric_id, reporting_basis, period_end_date)
)
"""

_QUARTERLY_DDL = """
CREATE TABLE IF NOT EXISTS market_data.stock_quarterly_fundamental_values (
  stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
  metric_id uuid NOT NULL REFERENCES market_data.fundamental_metric_reference(metric_id),
  period_start_date date,
  period_end_date date NOT NULL,
  reporting_basis varchar(20) NOT NULL CHECK (reporting_basis IN ('CONSOLIDATED', 'STANDALONE')),
  metric_value numeric(30, 10),
  source_id uuid REFERENCES market_data.data_sources(source_id),
  publication_date date,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (stock_id, metric_id, reporting_basis, period_end_date)
)
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(_ANNUAL_DDL)
    op.execute(_QUARTERLY_DDL)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_annual_fundamentals_period "
        "ON market_data.stock_annual_fundamental_values"
        "(stock_id, reporting_basis, period_end_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_quarterly_fundamentals_period "
        "ON market_data.stock_quarterly_fundamental_values"
        "(stock_id, reporting_basis, period_end_date)"
    )

    # Annual rows copy as-is.
    op.execute(
        """
        INSERT INTO market_data.stock_annual_fundamental_values
          (stock_id, metric_id, period_start_date, period_end_date, reporting_basis,
           metric_value, source_id, publication_date, version, created_at, updated_at)
        SELECT
          v.stock_id, v.metric_id, v.period_start_date, v.period_end_date, v.reporting_basis,
          v.metric_value, v.source_id, v.publication_date, v.version, v.created_at, v.updated_at
        FROM market_data.stock_fundamental_values v
        WHERE v.reporting_period = 'ANNUAL'
        ON CONFLICT (stock_id, metric_id, reporting_basis, period_end_date) DO NOTHING
        """
    )

    # Quarterly: only PL metrics (skip mid-year BS/CF orphans).
    op.execute(
        """
        INSERT INTO market_data.stock_quarterly_fundamental_values
          (stock_id, metric_id, period_start_date, period_end_date, reporting_basis,
           metric_value, source_id, publication_date, version, created_at, updated_at)
        SELECT
          v.stock_id, v.metric_id, v.period_start_date, v.period_end_date, v.reporting_basis,
          v.metric_value, v.source_id, v.publication_date, v.version, v.created_at, v.updated_at
        FROM market_data.stock_fundamental_values v
        JOIN market_data.fundamental_metric_reference r ON r.metric_id = v.metric_id
        WHERE v.reporting_period = 'QUARTERLY'
          AND r.statement_type = 'PL'
        ON CONFLICT (stock_id, metric_id, reporting_basis, period_end_date) DO NOTHING
        """
    )

    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_fundamentals_period")
    op.execute("DROP TABLE IF EXISTS market_data.stock_fundamental_values")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS market_data.stock_fundamental_values (
          stock_id uuid NOT NULL REFERENCES market_data.stock_reference(stock_id),
          metric_id uuid NOT NULL REFERENCES market_data.fundamental_metric_reference(metric_id),
          reporting_period varchar(20) NOT NULL CHECK (reporting_period IN ('QUARTERLY', 'ANNUAL')),
          period_start_date date,
          period_end_date date NOT NULL,
          reporting_basis varchar(20) NOT NULL CHECK (reporting_basis IN ('CONSOLIDATED', 'STANDALONE')),
          metric_value numeric(30, 10),
          source_id uuid REFERENCES market_data.data_sources(source_id),
          publication_date date,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          UNIQUE (stock_id, metric_id, reporting_period, reporting_basis, period_end_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_stock_fundamentals_period "
        "ON market_data.stock_fundamental_values"
        "(stock_id, reporting_period, reporting_basis, period_end_date)"
    )
    op.execute(
        """
        INSERT INTO market_data.stock_fundamental_values
          (stock_id, metric_id, reporting_period, period_start_date, period_end_date,
           reporting_basis, metric_value, source_id, publication_date, version, created_at, updated_at)
        SELECT
          stock_id, metric_id, 'ANNUAL', period_start_date, period_end_date,
          reporting_basis, metric_value, source_id, publication_date, version, created_at, updated_at
        FROM market_data.stock_annual_fundamental_values
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO market_data.stock_fundamental_values
          (stock_id, metric_id, reporting_period, period_start_date, period_end_date,
           reporting_basis, metric_value, source_id, publication_date, version, created_at, updated_at)
        SELECT
          stock_id, metric_id, 'QUARTERLY', period_start_date, period_end_date,
          reporting_basis, metric_value, source_id, publication_date, version, created_at, updated_at
        FROM market_data.stock_quarterly_fundamental_values
        ON CONFLICT DO NOTHING
        """
    )
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_quarterly_fundamentals_period")
    op.execute("DROP INDEX IF EXISTS market_data.ix_stock_annual_fundamentals_period")
    op.execute("DROP TABLE IF EXISTS market_data.stock_quarterly_fundamental_values")
    op.execute("DROP TABLE IF EXISTS market_data.stock_annual_fundamental_values")
