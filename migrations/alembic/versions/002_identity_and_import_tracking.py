"""add user identity, asset class, and import tracking"""
from alembic import op
import sqlalchemy as sa

revision = "002_identity_and_import_tracking"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("full_name", sa.String(255)))
    op.add_column("users", sa.Column("pan", sa.String(20)))
    with op.batch_alter_table("users") as batch:
        batch.create_unique_constraint("uq_users_pan", ["pan"])
    op.add_column("assets", sa.Column("investment_class", sa.String(20), nullable=False, server_default="EQUITY"))
    op.add_column("transactions", sa.Column("source_file", sa.String(500)))
    op.add_column("transactions", sa.Column("source_row", sa.Integer))
    op.create_index("ix_transactions_source", "transactions", ["source_file", "source_row"], unique=True)

def downgrade():
    op.drop_index("ix_transactions_source", table_name="transactions")
    op.drop_column("transactions", "source_row")
    op.drop_column("transactions", "source_file")
    op.drop_column("assets", "investment_class")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("uq_users_pan", type_="unique")
    op.drop_column("users", "pan")
    op.drop_column("users", "full_name")
