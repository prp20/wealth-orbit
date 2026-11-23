# Portfolio vault crypto + JSON contract (v1)

Shared wire format for PC (Python) and Android (Kotlin). Do not change without bumping `schema_version` / ciphertext `version` and updating both clients.

## Ciphertext binary layout

**Key derivation:** UTF-8 secret string → SHA-256 → 32-byte AES key.  
(v1 assumes a high-entropy API-key-style secret; no Argon2/scrypt.)

**Cleartext:** UTF-8 JSON (schema below).

**Wire bytes (before Base64):**

| Field | Size | Notes |
|-------|------|-------|
| `version` | 1 byte | `0x01` |
| `nonce` | 12 bytes | Random per encrypt |
| `body` | variable | AES-GCM ciphertext \|\| 16-byte tag (Java/`Cipher` and Python `AESGCM` default) |

**DB column `ciphertext`:** standard Base64 (ASCII) of the wire bytes above.

**AAD (associated data):** UTF-8 string:

```text
wealth-orbit-portfolio-v1|{user_id}|{vault_generation}
```

Binds ciphertext to the owning user and vault generation so rows cannot be swapped across users or after reset.

## PortfolioSnapshot JSON (`schema_version` = 1)

```json
{
  "schema_version": 1,
  "exported_at": "2026-11-23T00:00:00+00:00",
  "portfolio_id": "22222222-2222-2222-2222-222222222222",
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
```

**Decimals:** always JSON strings (not numbers) to avoid float drift across Python/Kotlin. Format with fixed-point `format(d, "f")` (no scientific notation).

**Enums:** string values match `portfolio-service/backend/models.py` (`AssetType`, `AssetStatus`, `TransactionType`).

## Related

- Design: [2026-11-23-multi-client-e2e-portfolio-design.md](./2026-11-23-multi-client-e2e-portfolio-design.md)
- Plan: [2026-11-23-multi-client-e2e-portfolio-plan.md](./2026-11-23-multi-client-e2e-portfolio-plan.md)
