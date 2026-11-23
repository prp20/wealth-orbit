-- Template: GitHub Actions market writer role (session pooler).
-- Run as a privileged Supabase/Postgres user, then store a Session pooler URI
-- for this role as GitHub Actions secret MARKET_DATABASE_URL.
--
-- This role MUST NOT read or write public.portfolio_vault.
-- Adjust password before running.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gha_market_writer') THEN
    CREATE ROLE gha_market_writer LOGIN PASSWORD 'replace-with-strong-password';
  END IF;
END $$;

GRANT USAGE ON SCHEMA market_data TO gha_market_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA market_data TO gha_market_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA market_data TO gha_market_writer;

ALTER DEFAULT PRIVILEGES IN SCHEMA market_data
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gha_market_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA market_data
  GRANT USAGE, SELECT ON SEQUENCES TO gha_market_writer;

-- Explicitly deny vault access (table may not exist yet on older DBs — ignore).
DO $$
BEGIN
  IF to_regclass('public.portfolio_vault') IS NOT NULL THEN
    REVOKE ALL ON TABLE public.portfolio_vault FROM gha_market_writer;
  END IF;
END $$;

-- Optional hardening: no CREATE privileges outside market_data
REVOKE CREATE ON SCHEMA public FROM gha_market_writer;

-- Then in Supabase: Session pooler URI with user gha_market_writer →
-- GitHub repo Settings → Secrets → MARKET_DATABASE_URL
