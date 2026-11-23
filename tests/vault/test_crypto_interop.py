from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.vault.crypto import decrypt_snapshot, derive_key, encrypt_snapshot

SECRET = "test-portfolio-secret-do-not-use-in-prod-32b"
USER = "11111111-1111-1111-1111-111111111111"
GEN = 1
PLAIN = (
    '{"schema_version":1,"exported_at":"2026-11-23T00:00:00+00:00",'
    '"portfolio_id":"22222222-2222-2222-2222-222222222222",'
    '"assets":[],"transactions":[],"holdings":[]}'
)


def test_derive_key_is_32_bytes():
    assert len(derive_key(SECRET)) == 32


def test_round_trip():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    assert decrypt_snapshot(ct, secret=SECRET, user_id=USER, vault_generation=GEN) == PLAIN


def test_wrong_generation_fails():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    with pytest.raises(Exception):
        decrypt_snapshot(ct, secret=SECRET, user_id=USER, vault_generation=GEN + 1)


def test_wrong_user_fails():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    with pytest.raises(Exception):
        decrypt_snapshot(
            ct,
            secret=SECRET,
            user_id="99999999-9999-9999-9999-999999999999",
            vault_generation=GEN,
        )


def test_wire_has_version_byte():
    ct = encrypt_snapshot(PLAIN, secret=SECRET, user_id=USER, vault_generation=GEN)
    raw = base64.b64decode(ct)
    assert raw[0] == 0x01
    assert len(raw) > 1 + 12 + 16
