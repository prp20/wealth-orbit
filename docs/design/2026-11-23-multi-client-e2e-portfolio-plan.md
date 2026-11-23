# Multi-client E2E Portfolio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship dual-client Wealth Orbit with a single AES-256-GCM encrypted portfolio document in Supabase, PC + Kotlin Android clients that share one secret, GitHub Actions for market_data refresh, and an optional Groq agent on Android.

**Architecture:** Supabase holds plaintext `market_data` and opaque portfolio ciphertext. PC connects via **session pooler** `DATABASE_URL` in `.env` (same as today) and encrypts/decrypts with `PORTFOLIO_ENCRYPTION_SECRET`. Android (Kotlin) later uses Auth JWT + anon key (not the pooler password). GHA writes market data only. Android is market read-only and never performs vault reset.

**Tech Stack:** Python 3 + FastAPI + existing `portfolio-service`; Supabase Auth + Postgres; Alembic; AES-256-GCM; Kotlin + Jetpack Compose (`minSdk 24`); OkHttp/Ktor → Groq OpenAI-compatible API; GitHub Actions + existing seed/sync scripts.

**Spec:** [2026-11-23-multi-client-e2e-portfolio-design.md](./2026-11-23-multi-client-e2e-portfolio-design.md)

## Global Constraints

- Portfolio plaintext never stored or logged on Supabase, GHA, or Edge Functions
- Encryption: AES-256-GCM; shared API-key-style secret; PC secret only in `.env` as `PORTFOLIO_ENCRYPTION_SECRET`
- Android: Kotlin + Jetpack Compose; `minSdk = 24`; lightweight (no bulk OHLC sync, no on-device LLM)
- Android may write portfolio ciphertext only; market paths read-only; no vault reset UI
- Groq: user-supplied API key on device; `skill.md` Android-local only
- Lost encryption secret ⇒ ciphertext unrecoverable; reset is PC-only
- Do not commit secrets; do not put portfolio secret in GitHub Actions secrets

## Subsystem split (execute as sequenced PRs)

| Wave | Deliverable | Can ship alone? |
|------|-------------|-----------------|
| **A** | Crypto contract + golden vectors (Python) | Yes (library + tests) |
| **B** | Supabase vault table + Auth + RLS | Yes (schema + SQL policies) |
| **C** | PC FastAPI vault sync + migrate + reset | Yes (PC dual-client SoT) |
| **D** | GitHub Actions market refresh | Yes (ops) |
| **E** | Android app (auth, vault, market read, Groq) | Needs A–C |

Prefer one PR per wave. Do not start Wave E until Wave A golden vectors exist (Android must match them).

## File map (new / primary)

| Path | Responsibility |
|------|----------------|
| `docs/design/portfolio-vault-crypto.md` | Byte layout + JSON schema (human contract) |
| `portfolio-service/backend/vault/crypto.py` | AES-GCM encrypt/decrypt |
| `portfolio-service/backend/vault/schema.py` | Plaintext snapshot dataclasses + JSON serde |
| `portfolio-service/backend/vault/sqlite_export.py` | SQLite ledger → snapshot |
| `portfolio-service/backend/vault/repository.py` | Supabase/Postgres vault row IO |
| `backend_api/app/vault_routes.py` | PC HTTP: get/put vault, reset |
| `migrations/alembic/versions/018_portfolio_vault.py` | `portfolio_vault` table (public or `app` schema) |
| `supabase/rls_portfolio_vault.sql` | RLS policies (applied in Supabase SQL editor or migration) |
| `.github/workflows/market-data-refresh.yml` | Scheduled market sync |
| `android/` | Kotlin Compose app module root |
| `tests/vault/test_crypto_interop.py` | Golden vector tests |

---

### Task 1: Document crypto + portfolio JSON contract

**Files:**
- Create: `docs/design/portfolio-vault-crypto.md`
- Modify: `docs/design/2026-11-23-multi-client-e2e-portfolio-design.md` (link §6.1 / §7 to this contract)
- Modify: `docs/README.md` (link under Architecture)

**Interfaces:**
- Produces: ciphertext layout and JSON field names that Tasks 2–3 and Android must implement verbatim

- [ ] **Step 1: Write the contract file**

Create `docs/design/portfolio-vault-crypto.md` with exactly:

```markdown
# Portfolio vault crypto + JSON contract (v1)

## Ciphertext binary layout

Key: UTF-8 secret string → SHA-256 → 32-byte AES key
  (do not use raw password stretching in v1; secret is already high-entropy)

Cleartext bytes: UTF-8 JSON (see schema below)

Wire format (before DB storage):
  version: 1 byte = 0x01
  nonce:   12 bytes (random per encrypt)
  body:    ciphertext \|\| 16-byte GCM tag  (Java/Android Cipher default order)

DB column `ciphertext`: standard Base64 of (version \|\| nonce \|\| body)
AAD: UTF-8 string `wealth-orbit-portfolio-v1|{user_id}|{vault_generation}`
  (bind ciphertext to user + generation so rows cannot be swapped)

## PortfolioSnapshot JSON (schema_version = 1)

{
  "schema_version": 1,
  "exported_at": "ISO-8601 timestamptz",
  "portfolio_id": "uuid",
  "assets": [
    {
      "asset_id": "uuid",
      "asset_type": "STOCK|MUTUAL_FUND|FIXED_DEPOSIT|BOND",
      "external_id": "string",
      "asset_name": "string",
      "investment_class": "string",
      "status": "ACTIVE|INACTIVE"
    }
  ],
  "transactions": [
    {
      "transaction_id": "uuid",
      "asset_id": "uuid",
      "transaction_type": "BUY|SELL",
      "quantity": "decimal-as-string",
      "price_per_unit": "decimal-as-string",
      "transaction_amount": "decimal-as-string",
      "transaction_date": "YYYY-MM-DD",
      "source_file": null,
      "source_row": null
    }
  ],
  "holdings": [
    {
      "holding_id": "uuid",
      "asset_id": "uuid",
      "current_quantity": "decimal-as-string",
      "invested_amount": "decimal-as-string",
      "average_cost_per_unit": "decimal-as-string"
    }
  ]
}

Decimals are strings to avoid float drift across Python/Kotlin.
```

- [ ] **Step 2: Link from handbook**

In `docs/README.md` Architecture section add:

```markdown
- [design/portfolio-vault-crypto.md](design/portfolio-vault-crypto.md) — vault ciphertext + JSON contract
```

- [ ] **Step 3: Commit**

```bash
git add docs/design/portfolio-vault-crypto.md docs/README.md docs/design/2026-11-23-multi-client-e2e-portfolio-design.md
git commit -m "docs: add portfolio vault crypto and JSON contract"
```

---

### Task 2: Python AES-GCM vault crypto (TDD)

**Files:**
- Create: `portfolio-service/backend/vault/__init__.py`
- Create: `portfolio-service/backend/vault/crypto.py`
- Create: `tests/vault/test_crypto_interop.py`

**Interfaces:**
- Produces:
  - `derive_key(secret: str) -> bytes`  # 32 bytes
  - `encrypt_snapshot(plaintext_json: str, *, secret: str, user_id: str, vault_generation: int) -> str`  # base64 wire
  - `decrypt_snapshot(ciphertext_b64: str, *, secret: str, user_id: str, vault_generation: int) -> str`

- [ ] **Step 1: Write failing tests with fixed golden vector**

```python
# tests/vault/test_crypto_interop.py
import base64
from portfolio_service_path_fix import encrypt_snapshot, decrypt_snapshot, derive_key
# Adjust import to match package layout used in repo (see pyproject pythonpath).

SECRET = "test-portfolio-secret-do-not-use-in-prod-32b"
USER = "11111111-1111-1111-1111-111111111111"
GEN = 1
PLAIN = '{"schema_version":1,"exported_at":"2026-11-23T00:00:00+00:00","portfolio_id":"22222222-2222-2222-2222-222222222222","assets":[],"transactions":[],"holdings":[]}'

def test_derive_key_is_32_bytes():
    assert len(derive_key(SECRET)) == 32

def test_round_trip():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    assert decrypt_snapshot(ct, secret=SECRET, user_id=USER, vault_generation=GEN) == PLAIN

def test_wrong_generation_fails():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    try:
        decrypt_snapshot(ct, secret=SECRET, user_id=USER, vault_generation=GEN + 1)
        assert False, "expected failure"
    except Exception:
        pass

def test_wire_has_version_byte():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    raw = base64.b64decode(ct)
    assert raw[0] == 0x01
    assert len(raw) > 1 + 12 + 16
```

- [ ] **Step 2: Run tests — expect FAIL (module missing)**

```bash
cd /home/prasad/dev_home/portfolio_mf_stocks_project
uv run pytest tests/vault/test_crypto_interop.py -v
```

Expected: `ModuleNotFoundError` or import error

- [ ] **Step 3: Implement `crypto.py`**

```python
# portfolio-service/backend/vault/crypto.py
from __future__ import annotations
import base64
import hashlib
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = b"\x01"
AAD_PREFIX = "wealth-orbit-portfolio-v1"


def derive_key(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _aad(user_id: str, vault_generation: int) -> bytes:
    return f"{AAD_PREFIX}|{user_id}|{vault_generation}".encode("utf-8")


def encrypt_snapshot(
    plaintext_json: str, *, secret: str, user_id: str, vault_generation: int
) -> str:
    key = derive_key(secret)
    nonce = os.urandom(12)
    aes = AESGCM(key)
    body = aes.encrypt(nonce, plaintext_json.encode("utf-8"), _aad(user_id, vault_generation))
    return base64.b64encode(VERSION + nonce + body).decode("ascii")


def decrypt_snapshot(
    ciphertext_b64: str, *, secret: str, user_id: str, vault_generation: int
) -> str:
    raw = base64.b64decode(ciphertext_b64)
    if len(raw) < 1 + 12 + 16 or raw[0:1] != VERSION:
        raise ValueError("unsupported ciphertext")
    nonce, body = raw[1:13], raw[13:]
    aes = AESGCM(derive_key(secret))
    pt = aes.decrypt(nonce, body, _aad(user_id, vault_generation))
    return pt.decode("utf-8")
```

Ensure `cryptography` is already a dependency or add it to `pyproject.toml`.

- [ ] **Step 4: Fix imports / package path; run tests PASS**

```bash
uv run pytest tests/vault/test_crypto_interop.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add portfolio-service/backend/vault tests/vault pyproject.toml
git commit -m "feat(vault): add AES-GCM portfolio encrypt/decrypt with golden tests"
```

---

### Task 3: Snapshot schema + SQLite export

**Files:**
- Create: `portfolio-service/backend/vault/schema.py`
- Create: `portfolio-service/backend/vault/sqlite_export.py`
- Create: `tests/vault/test_sqlite_export.py`
- Read: `portfolio-service/backend/models.py` (User, Portfolio, Asset, Transaction, Holding)

**Interfaces:**
- Consumes: SQLAlchemy models / session from existing portfolio DB
- Produces:
  - `snapshot_to_json(snapshot: PortfolioSnapshot) -> str`
  - `json_to_snapshot(data: str) -> PortfolioSnapshot`
  - `export_portfolio_from_sqlite(session, portfolio_id: UUID) -> PortfolioSnapshot`

- [ ] **Step 1: Write failing export test** (use in-memory SQLite or fixture DB)

```python
def test_export_includes_holding_decimal_as_string(session_with_one_buy):
    snap = export_portfolio_from_sqlite(session_with_one_buy, portfolio_id)
    raw = snapshot_to_json(snap)
    assert '"schema_version": 1' in raw or '"schema_version":1' in raw
    assert snap.holdings[0].current_quantity  # string type
    assert isinstance(snap.holdings[0].current_quantity, str)
```

- [ ] **Step 2: Implement schema + export mapping every field from the contract**

Map from `models.py`: assets, transactions, holdings; decimals via `format(d, "f")` or `str(d)` consistently (document choice in contract: use normalized string without scientific notation).

- [ ] **Step 3: Run tests PASS**

```bash
uv run pytest tests/vault/test_sqlite_export.py tests/vault/test_crypto_interop.py -v
```

- [ ] **Step 4: Commit**

```bash
git add portfolio-service/backend/vault tests/vault
git commit -m "feat(vault): export SQLite portfolio to encrypted snapshot JSON"
```

---

### Task 4: Alembic portfolio_vault table

**Files:**
- Create: `migrations/alembic/versions/018_portfolio_vault.py` (use actual next revision id after checking `alembic heads`)
- Modify: `docs/data/overview.md` (mention vault ciphertext store)

**Interfaces:**
- Produces table (schema `public` or `app` — prefer `public.portfolio_vault` for simple Supabase RLS):

```sql
create table public.portfolio_vault (
  user_id uuid primary key references auth.users (id) on delete cascade,
  vault_generation int not null default 1,
  version int not null default 1,
  ciphertext text not null,
  updated_at timestamptz not null default now()
);
```

Note: `auth.users` exists only on hosted Supabase. For local Alembic against plain Postgres without Auth, either:
- create a stub `auth` schema + `users` table in a Supabase-only migration path, **or**
- use `user_id uuid primary key` without FK in Alembic and add FK via Supabase SQL editor.

**Locked for this plan:** Alembic creates table **without** FK to `auth.users`; separate SQL file adds FK + RLS on Supabase.

- [ ] **Step 1: Check current head**

```bash
uv run alembic -c migrations/alembic.ini heads
```

- [ ] **Step 2: Write migration creating `portfolio_vault` as above (no auth FK)**

- [ ] **Step 3: Apply on dev database**

```bash
uv run alembic -c migrations/alembic.ini upgrade head
```

Expected: success; `\d portfolio_vault` shows columns

- [ ] **Step 4: Commit**

```bash
git add migrations/alembic/versions/018_portfolio_vault.py docs/data/overview.md
git commit -m "feat(db): add portfolio_vault table for E2E ciphertext"
```

---

### Task 5: Supabase Auth + RLS policies

**Files:**
- Create: `supabase/rls_portfolio_vault.sql`
- Create: `supabase/grants_market_reader.sql`
- Modify: `docs/setup.md` (Auth enable steps + apply SQL)
- Modify: `.env.example` (add Supabase URL + anon key placeholders; `PORTFOLIO_ENCRYPTION_SECRET`)

**Interfaces:**
- Produces SQL operators apply once per project

- [ ] **Step 1: Write RLS SQL**

```sql
-- supabase/rls_portfolio_vault.sql
alter table public.portfolio_vault enable row level security;

create policy portfolio_vault_select_own on public.portfolio_vault
  for select to authenticated
  using (auth.uid() = user_id);

create policy portfolio_vault_insert_own on public.portfolio_vault
  for insert to authenticated
  with check (auth.uid() = user_id);

create policy portfolio_vault_update_own on public.portfolio_vault
  for update to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- No delete for authenticated (reset uses service role on PC only)
revoke all on public.portfolio_vault from anon;
```

Market: ensure `authenticated` / `anon` have **SELECT only** on `market_data` tables used by mobile; **no INSERT/UPDATE/DELETE**. Put explicit `revoke insert, update, delete` on those tables for `authenticated` in `grants_market_reader.sql`.

- [ ] **Step 2: Document setup**

Add to `docs/setup.md`: enable Email auth; create test user; run SQL; set env:

```bash
SUPABASE_URL=https://PROJECT.supabase.co
SUPABASE_ANON_KEY=...
PORTFOLIO_ENCRYPTION_SECRET=generate-a-long-random-string
# PC vault reset only:
SUPABASE_SERVICE_ROLE_KEY=...   # never ship to Android
```

- [ ] **Step 3: Manual verify**

With user JWT: `select` own row OK; other `user_id` denied. With user JWT: `insert into market_data...` fails.

- [ ] **Step 4: Commit**

```bash
git add supabase docs/setup.md .env.example
git commit -m "feat(supabase): RLS for portfolio_vault and market read-only grants"
```

---

### Task 6: PC vault repository + FastAPI routes

**Files:**
- Create: `portfolio-service/backend/vault/repository.py`
- Create: `backend_api/app/vault_routes.py`
- Modify: `backend_api/app/main.py` (include router)
- Create: `tests/vault/test_vault_routes.py` (httpx + mocked repo or testcontainers if already used)

**Interfaces:**
- Produces HTTP (cookie or Bearer — prefer Supabase JWT validation on these routes for v1 cloud path):
  - `GET /api/v1/vault` → `{ vault_generation, version, ciphertext, updated_at }`
  - `PUT /api/v1/vault` body `{ version, ciphertext }` optimistic concurrency; server sets `user_id` from auth
  - `POST /api/v1/vault/reset` → deletes row / inserts empty marker, returns `new_vault_generation`; **requires service role or elevated PC session**; body confirmation `{"confirm":"RESET"}`

PC encrypt path (server-side with env secret):
  - `POST /api/v1/vault/push-from-sqlite` — export SQLite → encrypt → upsert (migration helper)
  - `POST /api/v1/vault/pull-to-memory` — decrypt for PC UI (never log plaintext)

- [ ] **Step 1: Failing API test for optimistic concurrency**

```python
def test_put_rejects_stale_version(client, auth_header):
    # seed version=1
    r = client.put("/api/v1/vault", json={"version": 1, "ciphertext": "aaa"}, headers=auth_header)
    assert r.status_code == 409  # when current version is already 2
```

- [ ] **Step 2: Implement repository using `DATABASE_URL` or Supabase REST**

**Locked:** PC FastAPI vault IO uses the existing **session pooler** `DATABASE_URL` / `ALEMBIC_DATABASE_URL` (psycopg), same as market data — not PostgREST and not Email Auth. Encrypt/decrypt with `PORTFOLIO_ENCRYPTION_SECRET` from `.env`. Map vault owner via `SUPABASE_USER_ID` (or local config) until Android Auth lands in Wave E.

- [ ] **Step 3: Wire router in `main.py`; tests PASS**

- [ ] **Step 4: Commit**

```bash
git add backend_api/app/vault_routes.py backend_api/app/main.py portfolio-service/backend/vault tests/vault
git commit -m "feat(api): portfolio vault get/put/reset endpoints"
```

---

### Task 7: PC migration cutover (SQLite → vault)

**Files:**
- Create: `portfolio-service/scripts/vault_migrate_push.py`
- Modify: `docs/getting-started.md` / `docs/setup.md` (migration steps)
- Optional feature flag: `PORTFOLIO_SOURCE=sqlite|vault` in env

**Interfaces:**
- Produces CLI:

```bash
uv run python portfolio-service/scripts/vault_migrate_push.py --user-access-token "$TOKEN"
```

- [ ] **Step 1: Script loads SQLite portfolio for mapped user, encrypts with `PORTFOLIO_ENCRYPTION_SECRET`, PUTs vault**

Map local SQLite user → Supabase `auth.users` id via env `SUPABASE_USER_ID` for v1 (explicit; no magic email join yet).

- [ ] **Step 2: Dry-run flag prints snapshot stats without upload**

- [ ] **Step 3: Document cutover:** push once → set `PORTFOLIO_SOURCE=vault` → PC UI reads vault

- [ ] **Step 4: Commit**

```bash
git add portfolio-service/scripts/vault_migrate_push.py docs/setup.md docs/getting-started.md
git commit -m "feat(vault): CLI to push SQLite portfolio into encrypted Supabase vault"
```

---

### Task 8: PC vault reset UX (API-first, minimal UI)

**Files:**
- Modify: `backend_api/app/vault_routes.py` (reset already from Task 6)
- Modify: `frontend-react` — small settings page or button calling reset
- Create: `frontend-react/src/pages/VaultSettings.tsx` (or equivalent existing settings pattern)

**Interfaces:**
- UI requires typing `RESET`, then calls `POST /api/v1/vault/reset`
- Shows new secret generation instructions: rotate `PORTFOLIO_ENCRYPTION_SECRET` in `.env` manually after reset (v1: user generates secret offline; API does not invent secret into response body to avoid logging — document “generate locally, put in .env, paste on Android”)

- [ ] **Step 1: Minimal React form with confirm string**

- [ ] **Step 2: Manual test reset clears vault row / bumps generation**

- [ ] **Step 3: Commit**

```bash
git add frontend-react backend_api
git commit -m "feat(ui): PC-only portfolio vault reset confirmation"
```

---

### Task 9: GitHub Actions incremental market refresh

**Files:**
- Create: `.github/workflows/market-data-refresh.yml`
- Create: `portfolio-service/scripts/ci/refresh_market_incremental.py` (thin wrapper calling existing sync helpers)
- Modify: `docs/setup.md` (required GitHub secrets)

**Interfaces:**
- Secrets: `MARKET_DATABASE_URL` (role with write on `market_data` only — create DB user `gha_market_writer` in Supabase)
- No `PORTFOLIO_ENCRYPTION_SECRET`, no service role with vault access if avoidable

- [ ] **Step 1: Wrapper script**

```python
# refresh latest daily metrics / index quotes for seeded symbols only (S-tier)
# Reuse portfolio-service/backend/market_data providers; do not download max history
```

- [ ] **Step 2: Workflow**

```yaml
name: market-data-refresh
on:
  schedule:
    - cron: "17 12 * * 1-5"   # ~17:47 IST weekdays; avoid :00
  workflow_dispatch:
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run python portfolio-service/scripts/ci/refresh_market_incremental.py
        env:
          DATABASE_URL: ${{ secrets.MARKET_DATABASE_URL }}
```

- [ ] **Step 3: Manual `workflow_dispatch` on a branch; verify rows update; confirm cannot `select` portfolio_vault with that role**

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/market-data-refresh.yml portfolio-service/scripts/ci docs/setup.md
git commit -m "ci: scheduled incremental market_data refresh"
```

---

### Task 10: Android project skeleton (minSdk 24)

**Files:**
- Create: `android/` Gradle project (Kotlin, Compose, minSdk 24, targetSdk current stable)
- Create: `android/README.md` (build, secrets, lightweight rules)

**Interfaces:**
- Produces installable empty app with navigation scaffold: Login, Home (market), Portfolio, Settings, Agent

- [ ] **Step 1: Android Studio / `gradle` init with Compose BOM; `minSdk = 24`**

- [ ] **Step 2: Dependencies — OkHttp or Ktor, kotlinx.serialization, security-crypto (EncryptedSharedPreferences), Supabase Kotlin or raw HTTP; no ML kits**

- [ ] **Step 3: Verify assemble**

```bash
cd android && ./gradlew :app:assembleDebug
```

Expected: BUILD SUCCESSFUL

- [ ] **Step 4: Commit**

```bash
git add android
git commit -m "feat(android): Compose app skeleton with minSdk 24"
```

---

### Task 11: Android crypto parity with Python golden vectors

**Files:**
- Create: `android/app/src/main/java/.../vault/VaultCrypto.kt`
- Create: `android/app/src/test/java/.../vault/VaultCryptoTest.kt`
- Read: `tests/vault/` golden outputs — export a fixed ciphertext from Python into the Android test

**Interfaces:**
- Produces Kotlin `encrypt` / `decrypt` matching Task 2 wire format and AAD

- [ ] **Step 1: Generate fixture from Python**

```bash
uv run python -c "from portfolio_service...crypto import encrypt_snapshot; print(encrypt_snapshot(...))"
```

Commit fixture string into Android unit test (or shared `testdata/vault_golden.txt` at repo root).

- [ ] **Step 2: Failing Android unit test decrypts Python ciphertext to expected JSON**

- [ ] **Step 3: Implement AES/GCM in Kotlin (`javax.crypto.Cipher`)**

- [ ] **Step 4:** `./gradlew :app:testDebugUnitTest` PASS

- [ ] **Step 5: Commit**

```bash
git add android testdata/vault_golden.txt
git commit -m "feat(android): AES-GCM vault crypto interoperable with Python"
```

---

### Task 12: Android Auth + vault get/put + settings

**Files:**
- `android/.../auth/SupabaseAuthRepository.kt`
- `android/.../vault/VaultRepository.kt`
- `android/.../ui/settings/SettingsScreen.kt`
- `android/.../ui/portfolio/PortfolioScreen.kt`

**Interfaces:**
- Settings stores: encryption secret + Groq key in EncryptedSharedPreferences
- Portfolio screen: fetch ciphertext → decrypt → show holdings list (read-only first); edit later optional
- Put path: bump version, encrypt, upsert; handle 409 retry

- [ ] **Step 1: Login with Supabase email/password (GoTrue REST)**

- [ ] **Step 2: Load vault row with user JWT; decrypt; render holdings**

- [ ] **Step 3: Save encryption secret; reject blank**

- [ ] **Step 4: Manual E2E with PC-pushed vault**

- [ ] **Step 5: Commit**

```bash
git add android
git commit -m "feat(android): auth, vault sync, and encrypted portfolio view"
```

---

### Task 13: Android market read-only screens

**Files:**
- `android/.../market/MarketRepository.kt`
- `android/.../ui/home/HomeScreen.kt`

**Interfaces:**
- SELECT-only queries: index latest levels, watchlist/latest metrics for a small symbol list
- No sync job enqueue; no writes

- [ ] **Step 1: Implement narrow PostgREST/SQL selects**

- [ ] **Step 2: UI shows 3–5 indexes + optional symbol quote**

- [ ] **Step 3: Confirm build stays lean (no unused deps)**

- [ ] **Step 4: Commit**

```bash
git add android
git commit -m "feat(android): lightweight read-only market home"
```

---

### Task 14: Android Groq agent + local skill.md

**Files:**
- `android/.../agent/GroqClient.kt`
- `android/.../agent/SkillLoader.kt`
- `android/.../ui/agent/AgentScreen.kt`
- Create sample: `android/app/src/main/assets/skill.md.example`

**Interfaces:**
- `GroqClient.chat(apiKey, messages) -> String` → `POST https://api.groq.com/openai/v1/chat/completions`
- Load `skill.md` from app private files dir (user-imported); fallback to short built-in system prompt
- Disclosure banner: portfolio context is sent to Groq
- No portfolio writes from agent

- [ ] **Step 1: Unit test GroqClient request JSON shape (mocked server)**

- [ ] **Step 2: AgentScreen composes skill + decrypted holdings summary + user question**

- [ ] **Step 3: Manual test with user Groq key**

- [ ] **Step 4: Commit**

```bash
git add android
git commit -m "feat(android): Groq agent with local skill.md"
```

---

### Task 15: Docs handbook refresh + success criteria checklist

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/data/overview.md`
- Modify: `docs/data/portfolio.md`
- Modify: `docs/design/2026-11-23-multi-client-e2e-portfolio-design.md` (check success criteria)

- [ ] **Step 1: Update architecture diagram for vault + Android + GHA**

- [ ] **Step 2: Mark design §15 checkboxes that are verified**

- [ ] **Step 3: Commit**

```bash
git add docs
git commit -m "docs: align handbook with multi-client E2E vault architecture"
```

---

## Guidance for implementers

1. **Order matters:** never build Android crypto before Python golden vectors.
2. **Secrets:** three different secrets (Auth password, encryption secret, Groq key). Name them differently in UI copy.
3. **Logging:** never log decrypted JSON or encryption secret. Redact ciphertext in debug logs if needed.
4. **Concurrency:** always send `version`; on 409, re-fetch, re-apply local edit, re-encrypt.
5. **Lightweight Android:** if a library pulls minSdk > 24 or adds ML, reject it.
6. **GHA role:** create a Postgres role that cannot touch `portfolio_vault`.
7. **Testing:** crypto tests are the contract; treat a failed interop test as a release blocker.

## Spec coverage (self-review)

| Spec section | Tasks |
|--------------|-------|
| E2E portfolio ciphertext | 1–3, 6–7, 11–12 |
| Supabase cannot read plaintext | 2, 5, 6 |
| Market plaintext + GHA | 5, 9, 13 |
| Android RO market / portfolio write | 5, 12–13 |
| Groq + skill.md | 14 |
| PC-only reset / lost key | 6, 8 |
| Kotlin Compose minSdk 24 lightweight | 10–14 |
| Migration from SQLite | 3, 7 |
| Notifications deferred | (explicit non-goal; no task) |

## Execution handoff

Plan saved to:

- Tracked: [`docs/design/2026-11-23-multi-client-e2e-portfolio-plan.md`](./2026-11-23-multi-client-e2e-portfolio-plan.md)
- Local mirror: `docs/superpowers/plans/2026-11-23-multi-client-e2e-portfolio.md`
