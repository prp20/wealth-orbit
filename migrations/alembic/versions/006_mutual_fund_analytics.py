"""Persist mutual-fund analytics and enrichment snapshots."""
from alembic import op

revision = "006_mutual_fund_analytics"
down_revision = "005_sync_job_force_uniqueness"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.index_daily_history (
      index_id uuid NOT NULL REFERENCES market_data.index_reference(index_id),
      history_date date NOT NULL, open numeric(24,8), high numeric(24,8), low numeric(24,8),
      close numeric(24,8) NOT NULL CHECK(close > 0), volume bigint, source_id uuid REFERENCES market_data.data_sources(source_id),
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(index_id, history_date))""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.mutual_fund_metric_snapshots (
      metric_snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), scheme_id uuid NOT NULL REFERENCES market_data.mutual_fund_reference(scheme_id),
      as_of_date date NOT NULL, metric_period varchar(10) NOT NULL,
      current_nav numeric(24,8), trailing_return numeric(18,10), cagr numeric(18,10),
      rolling_latest numeric(18,10), rolling_min numeric(18,10), rolling_max numeric(18,10), rolling_median numeric(18,10),
      standard_deviation numeric(18,10), sharpe numeric(18,10), sortino numeric(18,10), maximum_drawdown numeric(18,10),
      alpha numeric(18,10), beta numeric(18,10), tracking_error numeric(18,10), information_ratio numeric(18,10),
      benchmark_index_id uuid REFERENCES market_data.index_reference(index_id), benchmark_as_of_date date,
      observations integer NOT NULL DEFAULT 0, aligned_observations integer NOT NULL DEFAULT 0,
      risk_free_rate numeric(18,10), annualization_factor integer NOT NULL DEFAULT 252,
      available boolean NOT NULL DEFAULT true, reason text, calculation_version varchar(30) NOT NULL DEFAULT 'v1',
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(scheme_id, as_of_date, metric_period, calculation_version))""")
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.mutual_fund_enrichment (
      enrichment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), scheme_id uuid NOT NULL REFERENCES market_data.mutual_fund_reference(scheme_id),
      as_of_date date NOT NULL, aum numeric(30,8), expense_ratio numeric(18,10), exit_load text,
      yield_to_maturity numeric(18,10), yield_to_maturity_unit varchar(20), fund_manager text, rating text,
      source_id uuid REFERENCES market_data.data_sources(source_id), provider_status varchar(20) NOT NULL DEFAULT 'AVAILABLE',
      raw_payload_hash varchar(64), warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(scheme_id, as_of_date, source_id))""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mf_metrics_lookup ON market_data.mutual_fund_metric_snapshots(scheme_id, as_of_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_mf_enrichment_lookup ON market_data.mutual_fund_enrichment(scheme_id, as_of_date DESC)")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS market_data.mutual_fund_enrichment")
        op.execute("DROP TABLE IF EXISTS market_data.mutual_fund_metric_snapshots")
        op.execute("DROP TABLE IF EXISTS market_data.index_daily_history")
