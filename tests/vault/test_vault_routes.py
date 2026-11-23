from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def vault_client(tmp_path, monkeypatch):
    database = tmp_path / "portfolio.db"
    monkeypatch.setenv("PORTFOLIO_SQLITE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    monkeypatch.setenv("VAULT_USER_ID", "11111111-1111-1111-1111-111111111111")
    monkeypatch.setenv("PORTFOLIO_ENCRYPTION_SECRET", "unit-test-encryption-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused")

    from sqlalchemy import create_engine

    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "portfolio-service"))
    from backend.models import Base

    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    engine.dispose()

    from backend_api.app.main import app

    with TestClient(app) as client:
        signup = client.post(
            "/api/v1/auth/signup",
            json={"full_name": "Vault User", "password": "local-pass-99"},
        )
        assert signup.status_code == 200, signup.text
        yield client


def test_put_rejects_stale_version(vault_client, monkeypatch):
    from backend.vault import repository as repo

    def fake_put(**kwargs):
        raise repo.VaultConflictError("stale version: expected 1, remote 2")

    monkeypatch.setattr(repo, "put_vault", fake_put)
    # Re-bind routes module reference
    import backend_api.app.vault_routes as routes

    monkeypatch.setattr(routes, "put_vault", fake_put)

    r = vault_client.put(
        "/api/v1/vault",
        json={"version": 1, "ciphertext": "aaa", "vault_generation": 1},
    )
    assert r.status_code == 409


def test_get_vault_404_when_empty(vault_client, monkeypatch):
    import backend_api.app.vault_routes as routes

    monkeypatch.setattr(routes, "get_vault", lambda: None)
    r = vault_client.get("/api/v1/vault")
    assert r.status_code == 404


def test_get_vault_ok(vault_client, monkeypatch):
    import backend_api.app.vault_routes as routes

    row = SimpleNamespace(
        user_id="11111111-1111-1111-1111-111111111111",
        vault_generation=1,
        version=3,
        ciphertext="Y2lwaGVy",
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(routes, "get_vault", lambda: row)
    r = vault_client.get("/api/v1/vault")
    assert r.status_code == 200
    assert r.json()["version"] == 3
    assert r.json()["ciphertext"] == "Y2lwaGVy"


def test_reset_requires_confirm(vault_client):
    r = vault_client.post("/api/v1/vault/reset", json={"confirm": "nope"})
    assert r.status_code == 400


def test_reset_ok(vault_client, monkeypatch):
    import backend_api.app.vault_routes as routes

    monkeypatch.setattr(routes, "reset_vault", lambda: {"vault_generation": 2, "version": 0})
    r = vault_client.post("/api/v1/vault/reset", json={"confirm": "RESET"})
    assert r.status_code == 200
    assert r.json()["vault_generation"] == 2
