import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "portfolio-service"))

from backend_api.app.auth import hash_password, sign_session, verify_password, read_session


def test_password_hash_round_trip(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong horse", stored)
    token = sign_session("11111111-1111-1111-1111-111111111111", now=1_000)
    assert read_session(token, now=1_000) == "11111111-1111-1111-1111-111111111111"
    assert read_session(token + "x", now=1_000) is None


def test_portfolio_requires_the_local_session(tmp_path, monkeypatch):
    database = tmp_path / "portfolio.db"
    monkeypatch.setenv("PORTFOLIO_SQLITE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from backend.models import Base, Portfolio, User

    engine = create_engine(f"sqlite:///{database}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        owner = User(full_name="Pete", created_at=datetime(2020, 1, 1, tzinfo=timezone.utc), updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc))
        other = User(full_name="Other", created_at=datetime(2021, 1, 1, tzinfo=timezone.utc), updated_at=datetime(2021, 1, 1, tzinfo=timezone.utc))
        session.add_all([owner, other])
        session.flush()
        owner_book = Portfolio(user_id=owner.user_id)
        other_book = Portfolio(user_id=other.user_id)
        session.add_all([owner_book, other_book])
        session.commit()
        other_id = other_book.portfolio_id

    from fastapi.testclient import TestClient
    from backend_api.app.main import app

    with TestClient(app) as client:
        anonymous = client.get("/api/v1/auth/me")
        assert anonymous.status_code == 200
        assert anonymous.json()["signed_in"] is False
        assert client.get("/api/v1/portfolios").status_code == 401
        root = client.get("/ui", follow_redirects=False)
        assert root.status_code == 307
        assert root.headers["location"] == "/ui/"
        status = client.get("/api/v1/auth/status")
        assert status.status_code == 200
        assert status.json()["password_set"] is False

        signup = client.post("/api/v1/auth/signup", json={"full_name": "Ada", "password": "local-pass"})
        assert signup.status_code == 200
        assert signup.json()["signed_in"] is True
        listed = client.get("/api/v1/portfolios")
        assert listed.status_code == 200
        assert [row["user_name"] for row in listed.json()] == ["Ada"]
        assert client.get(f"/api/v1/portfolios/{other_id}/holdings").status_code == 404

        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/auth/me").json()["signed_in"] is False
        assert client.get("/api/v1/portfolios").status_code == 401
        wrong = client.post("/api/v1/auth/login", json={"full_name": "Ada", "password": "not-the-password"})
        assert wrong.status_code == 401
        assert wrong.json()["detail"] == "That name or password is not right."
        assert client.post("/api/v1/auth/login", json={"full_name": "Ada", "password": "local-pass"}).status_code == 200
