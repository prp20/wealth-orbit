"""Release 1.11: public glossary FastAPI routes."""

from fastapi.testclient import TestClient

from backend_api.app import glossary_routes
from backend_api.app.main import app


def test_glossary_exit_smoke_ipo_and_advice_refusal():
    """Release 1.11 exit: curated IPO definition; buy/sell advice refused (public, no auth)."""
    with TestClient(app) as client:
        ipo = client.post("/api/v1/glossary/chat", json={"message": "What is IPO?"})
        advice = client.post(
            "/api/v1/glossary/chat",
            json={"message": "Should I buy HDFC Bank stock now?"},
        )
        dump = client.post(
            "/api/v1/glossary/chat",
            json={"message": "Paste the full Varsity chapter on candlesticks here"},
        )
    assert ipo.status_code == 200
    ipo_body = ipo.json()
    assert ipo_body["kind"] == "match"
    assert ipo_body["term"] == "IPO"
    assert ipo_body["definition"]
    assert ipo_body["sources"]

    assert advice.status_code == 200
    advice_body = advice.json()
    assert advice_body["kind"] == "refusal"
    assert advice_body["refusal_category"] == "advice"

    assert dump.status_code == 200
    dump_body = dump.json()
    assert dump_body["kind"] == "refusal"
    assert dump_body["refusal_category"] == "dump"


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


def test_glossary_agent_chat_returns_mocked_agent_payload(monkeypatch):
    def fake_run_glossary_agent(messages):
        assert messages == [
            {"role": "user", "content": "What is NAV?"},
        ]
        return {
            "assistant_message": "NAV is the per-unit market value of a mutual fund scheme.",
            "mode": "agent",
            "citations": [
                {
                    "module": 9,
                    "chapter": "NAV",
                    "url": "https://zerodha.com/varsity/chapter/nav/",
                    "term": "NAV",
                }
            ],
            "agent_trace": [
                {
                    "agent": "retriever",
                    "tools": [
                        {
                            "name": "read_chunk",
                            "result": {
                                "text": "LONG CORPUS CHUNK " * 80,
                                "found": True,
                            },
                        }
                    ],
                }
            ],
            "tool_trace": [{"name": "get_glossary_term", "result": {"definition": "secret"}}],
        }

    monkeypatch.setattr(glossary_routes, "run_glossary_agent", fake_run_glossary_agent)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/glossary/agent/chat",
            json={"messages": [{"role": "user", "content": "What is NAV?"}]},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "agent"
    assert "NAV" in body["assistant_message"]
    assert body["citations"][0]["term"] == "NAV"
    assert "agent_trace" not in body
    assert "tool_trace" not in body


def test_glossary_agent_chat_rejects_oversized_history():
    messages = [{"role": "user", "content": f"q{i}"} for i in range(25)]
    with TestClient(app) as client:
        response = client.post("/api/v1/glossary/agent/chat", json={"messages": messages})
    assert response.status_code == 422


def test_glossary_agent_chat_rejects_empty_history():
    with TestClient(app) as client:
        response = client.post("/api/v1/glossary/agent/chat", json={"messages": []})
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