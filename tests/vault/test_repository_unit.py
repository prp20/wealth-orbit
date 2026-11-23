from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))

from backend.vault.repository import VaultConfigError, vault_user_id


def test_vault_user_id_required(monkeypatch):
    monkeypatch.delenv("VAULT_USER_ID", raising=False)
    with pytest.raises(VaultConfigError):
        vault_user_id()


def test_vault_user_id_valid(monkeypatch):
    monkeypatch.setenv("VAULT_USER_ID", "11111111-1111-1111-1111-111111111111")
    assert vault_user_id() == "11111111-1111-1111-1111-111111111111"
