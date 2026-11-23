"""Add public.portfolio_vault for E2E encrypted portfolio documents.

No FK to auth.users here — that exists only on hosted Supabase.
Apply supabase/rls_portfolio_vault.sql after this migration on Supabase
to enable RLS (optional FK to auth.users can be added there).
"""

from alembic import op

revision = "018_portfolio_vault"
down_revision = "017_stock_tech_calc_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.portfolio_vault (
          user_id uuid PRIMARY KEY,
          vault_generation integer NOT NULL DEFAULT 1,
          version integer NOT NULL DEFAULT 1,
          ciphertext text NOT NULL,
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT portfolio_vault_generation_positive CHECK (vault_generation >= 1),
          CONSTRAINT portfolio_vault_version_positive CHECK (version >= 1)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.portfolio_vault IS
          'E2E encrypted portfolio snapshot; plaintext never stored'
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TABLE IF EXISTS public.portfolio_vault")
