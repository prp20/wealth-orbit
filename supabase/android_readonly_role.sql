-- Template: restricted role for Android app (session pooler).
-- Run as a privileged Supabase/Postgres user, then create a pooler URI for this role
-- and paste that URI into Android setup — NOT the postgres superuser URL.
--
-- Adjust password before running.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wealth_orbit_android') THEN
    CREATE ROLE wealth_orbit_android LOGIN PASSWORD 'replace-with-strong-password';
  END IF;
END $$;

GRANT USAGE ON SCHEMA market_data TO wealth_orbit_android;
GRANT SELECT ON ALL TABLES IN SCHEMA market_data TO wealth_orbit_android;
ALTER DEFAULT PRIVILEGES IN SCHEMA market_data
  GRANT SELECT ON TABLES TO wealth_orbit_android;

-- Explicitly no market writes
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA market_data FROM wealth_orbit_android;

GRANT USAGE ON SCHEMA public TO wealth_orbit_android;
GRANT SELECT ON TABLE public.portfolio_vault TO wealth_orbit_android;

-- Optional: allow phone to update ciphertext (still no DELETE / reset)
-- GRANT INSERT, UPDATE ON TABLE public.portfolio_vault TO wealth_orbit_android;

-- Then in Supabase dashboard / connection strings, build a Session pooler URI
-- using user wealth_orbit_android and paste into Android setup.
