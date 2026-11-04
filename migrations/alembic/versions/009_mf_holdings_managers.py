"""Mutual-fund portfolio disclosures, holdings lines, and manager assignments."""
from alembic import op

revision = "009_mf_holdings_managers"
down_revision = "008_mutual_fund_fact_fields"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_portfolio_disclosures (
      disclosure_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      scheme_id uuid NOT NULL REFERENCES market_data.mutual_fund_reference(scheme_id),
      as_of_date date NOT NULL,
      source_name varchar(80) NOT NULL DEFAULT 'seed',
      source_id uuid REFERENCES market_data.data_sources(source_id),
      equity_pct numeric(18,10),
      debt_pct numeric(18,10),
      cash_pct numeric(18,10),
      other_pct numeric(18,10),
      raw_payload_hash varchar(64),
      warnings jsonb NOT NULL DEFAULT '[]'::jsonb,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(scheme_id, as_of_date, source_name))"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_portfolio_holdings (
      holding_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      disclosure_id uuid NOT NULL REFERENCES market_data.mutual_fund_portfolio_disclosures(disclosure_id) ON DELETE CASCADE,
      security_name text NOT NULL,
      isin varchar(20),
      sector text,
      market_cap_bucket varchar(20),
      instrument_type varchar(30) NOT NULL DEFAULT 'EQUITY',
      weight_pct numeric(18,10) NOT NULL CHECK (weight_pct >= 0),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now())"""
    )
    op.execute(
        """CREATE INDEX IF NOT EXISTS ix_mf_holdings_disclosure
           ON market_data.mutual_fund_portfolio_holdings(disclosure_id)"""
    )
    op.execute(
        """CREATE INDEX IF NOT EXISTS ix_mf_holdings_isin
           ON market_data.mutual_fund_portfolio_holdings(isin)"""
    )
    op.execute(
        """CREATE TABLE IF NOT EXISTS market_data.mutual_fund_manager_assignments (
      assignment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      scheme_id uuid NOT NULL REFERENCES market_data.mutual_fund_reference(scheme_id),
      manager_name text NOT NULL,
      start_date date NOT NULL,
      end_date date,
      is_current boolean NOT NULL DEFAULT true,
      source_name varchar(80) NOT NULL DEFAULT 'enrichment',
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE(scheme_id, manager_name, start_date))"""
    )
    op.execute(
        """CREATE INDEX IF NOT EXISTS ix_mf_manager_scheme
           ON market_data.mutual_fund_manager_assignments(scheme_id, is_current DESC, start_date DESC)"""
    )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TABLE IF EXISTS market_data.mutual_fund_portfolio_holdings")
        op.execute("DROP TABLE IF EXISTS market_data.mutual_fund_portfolio_disclosures")
        op.execute("DROP TABLE IF EXISTS market_data.mutual_fund_manager_assignments")
