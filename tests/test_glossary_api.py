"""Release 1.11: public glossary FastAPI routes."""

from fastapi.testclient import TestClient

from backend_api.app.main import app


def test_glossary_chat_match_without_auth():
    with TestClient(app) as client:
        response = client.post("/api/v1/glossary/chat", json={"message": "What is IPO?"})
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "match"
    assert body["term"] == "IPO"
    assert body["definition"]
    assert body["sources"]


def test_glossary_chat_refuses_advice_without_auth():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/glossary/chat",
            json={"message": "Should I buy HDFC Bank stock now?"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "refusal"
    assert body["refusal_category"] == "advice"


def test_glossary_chat_rejects_empty_message():
    with TestClient(app) as client:
        response = client.post("/api/v1/glossary/chat", json={"message": ""})
    assert response.status_code == 422


def test_glossary_terms_lists_seed_without_auth():
    with TestClient(app) as client:
        response = client.get("/api/v1/glossary/terms")
    assert response.status_code == 200
    terms = response.json()
    assert isinstance(terms, list)
    assert any(row["term"] == "IPO" for row in terms)
    ipo = next(row for row in terms if row["term"] == "IPO")
    assert any("public offering" in alias.lower() for alias in ipo["aliases"])