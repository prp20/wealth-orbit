-- Portfolio vault RLS for Supabase Auth.
-- Run in Supabase SQL editor AFTER Alembic migration 018_portfolio_vault.
-- Requires Auth enabled (email/password).

-- Optional: bind rows to auth.users (safe to re-run if already present)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'auth' AND table_name = 'users'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'portfolio_vault_user_id_fkey'
  ) THEN
    ALTER TABLE public.portfolio_vault
      ADD CONSTRAINT portfolio_vault_user_id_fkey
      FOREIGN KEY (user_id) REFERENCES auth.users (id) ON DELETE CASCADE;
  END IF;
END $$;

ALTER TABLE public.portfolio_vault ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS portfolio_vault_select_own ON public.portfolio_vault;
CREATE POLICY portfolio_vault_select_own ON public.portfolio_vault
  FOR SELECT TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS portfolio_vault_insert_own ON public.portfolio_vault;
CREATE POLICY portfolio_vault_insert_own ON public.portfolio_vault
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS portfolio_vault_update_own ON public.portfolio_vault;
CREATE POLICY portfolio_vault_update_own ON public.portfolio_vault
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- Authenticated clients must not delete vault rows (PC reset uses service role).
DROP POLICY IF EXISTS portfolio_vault_delete_own ON public.portfolio_vault;

REVOKE ALL ON TABLE public.portfolio_vault FROM anon;
GRANT SELECT, INSERT, UPDATE ON TABLE public.portfolio_vault TO authenticated;

-- Service role bypasses RLS by default in Supabase (used only on PC for vault reset).
