"""persisted market-data sync jobs"""
from alembic import op
revision="004_sync_jobs"; down_revision="003_stock_fundamentals_technical"; branch_labels=None; depends_on=None
def upgrade():
    if op.get_bind().dialect.name != "postgresql": return
    op.execute("""CREATE TABLE IF NOT EXISTS market_data.sync_jobs (
      job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), entity_type varchar(20) NOT NULL,
      entity_key varchar(255) NOT NULL, sync_type varchar(40) NOT NULL, force_sync boolean NOT NULL DEFAULT false,
      status varchar(20) NOT NULL DEFAULT 'QUEUED', progress_percent numeric(5,2) NOT NULL DEFAULT 0,
      records_total integer, records_processed integer NOT NULL DEFAULT 0, current_item varchar(255),
      queued_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, completed_at timestamptz,
      last_error text, result jsonb, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      CHECK(entity_type IN ('STOCK','MUTUAL_FUND')), CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED','CANCELLED')),
      CHECK(progress_percent BETWEEN 0 AND 100))""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sync_jobs_queue ON market_data.sync_jobs(status, queued_at)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active ON market_data.sync_jobs(entity_type,entity_key,sync_type,force_sync) WHERE status IN ('QUEUED','RUNNING')")
def downgrade():
    if op.get_bind().dialect.name == "postgresql": op.execute("DROP TABLE IF EXISTS market_data.sync_jobs")
