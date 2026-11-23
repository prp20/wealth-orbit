# Wealth Orbit Android

Lightweight Kotlin + Jetpack Compose client (`minSdk = 24`).

## What this app does

- Setup: paste a **restricted session pooler URL** (market SELECT-only role), encryption secret, `VAULT_USER_ID`, optional Groq key
- Portfolio: decrypt the single vault document on device
- Market: read-only index / quote SELECTs (no sync jobs)
- Agent: optional Groq chat with a local `skill.md`

## What this app does **not** do

- Bulk OHLC sync or on-device LLM
- Vault reset / DELETE on `portfolio_vault` (PC only)
- Embed the PC `DATABASE_URL` or service-role keys

## Build

```bash
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
cd android
./gradlew :app:assembleDebug
```

Install the APK from `app/build/outputs/apk/debug/`.

Unit tests:

```bash
./gradlew :app:testDebugUnitTest
```

## Secrets

Store only in EncryptedSharedPreferences after setup — never commit pooler passwords, encryption secrets, or Groq keys.

## Note on Postgres drivers

Use `org.postgresql:postgresql:42.2.27` (dexes on `minSdk 24`). Newer 42.7+ jars need API 26.
