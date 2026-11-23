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
