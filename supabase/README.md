# Supabase SQL for multi-client vault

## PC path

PC connects with the **session pooler** URI in `.env` (`DATABASE_URL` / `ALEMBIC_DATABASE_URL`, port 5432). That is enough for Alembic, market sync, and PC vault IO. **Email Auth is not required.**

## Android path (setup input)

1. Run [android_readonly_role.sql](./android_readonly_role.sql) (set a strong password).
2. Create a **Session** pooler connection string for role `wealth_orbit_android`.
3. On Android **setup**, paste that URI + `PORTFOLIO_ENCRYPTION_SECRET` + `VAULT_USER_ID`.

The Android role is **market SELECT-only**. Uncomment vault `INSERT`/`UPDATE` in the SQL only if you want phone portfolio edits. Never give Android the `postgres` superuser pooler URL.

## Optional: Auth + RLS

[rls_portfolio_vault.sql](./rls_portfolio_vault.sql) and [grants_market_reader.sql](./grants_market_reader.sql) are for a future anon-key/JWT client. Not required when Android uses a restricted pooler URL.
