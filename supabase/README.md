# Supabase SQL for multi-client vault

Apply in order after `alembic upgrade head` includes `018_portfolio_vault`:

1. [rls_portfolio_vault.sql](./rls_portfolio_vault.sql) — RLS on `public.portfolio_vault`
2. [grants_market_reader.sql](./grants_market_reader.sql) — `market_data` SELECT-only for `anon` / `authenticated`

Enable **Authentication → Providers → Email** in the Supabase dashboard before mobile/PC Auth login.

Do **not** put `SUPABASE_SERVICE_ROLE_KEY` or `PORTFOLIO_ENCRYPTION_SECRET` in the Android app.
