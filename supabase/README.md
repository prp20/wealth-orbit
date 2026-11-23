# Supabase SQL for multi-client vault

## PC path (what you use now)

The PC connects with the **session pooler** URI in `.env` (`DATABASE_URL` / `ALEMBIC_DATABASE_URL`, port 5432). That is enough for Alembic, market sync, and PC vault read/write. **Email Auth is not required for that.**

## Android / JWT path (Wave E — later)

When the phone uses the anon key (never the pooler password), apply in order after `018_portfolio_vault`:

1. [rls_portfolio_vault.sql](./rls_portfolio_vault.sql) — RLS on `public.portfolio_vault`
2. [grants_market_reader.sql](./grants_market_reader.sql) — `market_data` SELECT-only for `anon` / `authenticated`

Enable **Authentication → Providers → Email** only when you start the Android client.

Do **not** put `DATABASE_URL`, the pooler password, or `PORTFOLIO_ENCRYPTION_SECRET` in the Android app.
