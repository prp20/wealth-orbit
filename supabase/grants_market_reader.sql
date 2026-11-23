-- Market data: clients may SELECT only. Never grant write to anon/authenticated.
-- Run in Supabase SQL editor after market_data schema exists.
-- PC sync and GitHub Actions must use a privileged role (e.g. postgres or gha_market_writer),
-- not the anon/authenticated keys shipped to Android.

GRANT USAGE ON SCHEMA market_data TO anon, authenticated;

-- Read for mobile/PC user JWTs
GRANT SELECT ON ALL TABLES IN SCHEMA market_data TO anon, authenticated;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA market_data TO anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA market_data
  GRANT SELECT ON TABLES TO anon, authenticated;

-- Explicitly deny writes from client roles
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA market_data FROM anon, authenticated;
REVOKE INSERT, UPDATE, DELETE ON ALL SEQUENCES IN SCHEMA market_data FROM anon, authenticated;

-- Future tables: keep write revoked for client roles
ALTER DEFAULT PRIVILEGES IN SCHEMA market_data
  REVOKE INSERT, UPDATE, DELETE ON TABLES FROM anon, authenticated;

-- portfolio_vault is not in market_data; ensure anon cannot touch it
REVOKE ALL ON TABLE public.portfolio_vault FROM anon;
