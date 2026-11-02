"""Prevent force and incremental syncs from running concurrently."""
from alembic import op

revision = "005_sync_job_force_uniqueness"
down_revision = "004_sync_jobs"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS market_data.uq_sync_jobs_active")
    op.execute("""WITH ranked AS (
        SELECT job_id, row_number() OVER (
          PARTITION BY entity_type, entity_key, sync_type
          ORDER BY queued_at, created_at
        ) AS rn
        FROM market_data.sync_jobs
        WHERE status IN ('QUEUED','RUNNING')
      )
      UPDATE market_data.sync_jobs j
      SET status='FAILED', completed_at=now(), progress_percent=100,
          last_error='Superseded duplicate active sync during queue migration', updated_at=now()
      FROM ranked r
      WHERE j.job_id=r.job_id AND r.rn > 1""")
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active
        ON market_data.sync_jobs(entity_type, entity_key, sync_type)
        WHERE status IN ('QUEUED','RUNNING')""")


def downgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS market_data.uq_sync_jobs_active")
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uq_sync_jobs_active
        ON market_data.sync_jobs(entity_type, entity_key, sync_type, force_sync)
        WHERE status IN ('QUEUED','RUNNING')""")
