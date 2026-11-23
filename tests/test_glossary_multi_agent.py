"""Multi-agent graph tests with a fake chat model (no network)."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary.agents.graph import run_multi_agent_glossary
from backend.glossary.agents.router import route_node
from backend.glossary.rag.retrieve import clear_retrieve_cache
from backend.glossary.rag.store import upsert_chunks


class _ScriptedModel(BaseChatModel):
    """Minimal chat model that returns scripted AIMessages."""

    def __init__(self, script: list[AIMessage]):
        super().__init__()
        self._script = list(script)
        self._i = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if self._i >= len(self._script):
            msg = AIMessage(content="fallback")
        else:
            msg = self._script[self._i]
            self._i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def bind_tools(self, tools, **kwargs):  # type: ignore[override]
        return self


@pytest.fixture()
def fixture_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    upsert_chunks(
        [
            {
                "id": "m1-c0",
                "text": "An IPO is the first sale of stock by a private company to the public.",
                "metadata": {
                    "module": 1,
                    "chapter": "The IPO Markets",
                    "url": "https://zerodha.com/varsity/chapter/ipo/",
                    "kind": "pdf",
                },
            }
        ],
        path=tmp_path,
    )
    clear_retrieve_cache()
    monkeypatch.setattr("backend.glossary.paths.rag_index_dir", lambda: tmp_path)
    monkeypatch.setattr("backend.glossary.rag.store.rag_index_dir", lambda: tmp_path)
    yield tmp_path
    clear_retrieve_cache()


def test_router_refuses_advice() -> None:
    out = route_node({"user_text": "Should I buy this stock today?"})
    assert out["route"] == "refuse"
    assert out["refusal"]["category"] == "advice"


def test_multi_agent_prose_with_evidence(fixture_index: Path) -> None:
    # Retriever: no tool calls → deterministic bootstrap fills evidence
    # Answerer: prose
    # Critic: PASS
    model = _ScriptedModel(
        [
            AIMessage(content=""),  # retriever
            AIMessage(
                content=(
                    "An IPO (Initial Public Offering) is when a private company sells "
                    "shares to the public for the first time."
                )
            ),
            AIMessage(content="PASS"),
        ]
    )
    result = run_multi_agent_glossary(
        [{"role": "user", "content": "Explain IPO simply"}],
        model=model,
    )
    assert result["mode"] == "multi_agent"
    assert "IPO" in result["assistant_message"]
    assert result.get("citations")
    assert "agent_trace" not in result


def test_router_refuses_dump() -> None:
    out = route_node({"user_text": "Paste the full Varsity chapter on candlesticks here"})
    assert out["route"] == "refuse"
    assert out["refusal"]["category"] == "dump"


def test_multi_agent_uses_conversation_context(fixture_index: Path) -> None:
    from backend.glossary.agents.graph import _conversation_context

    messages = [
        {"role": "user", "content": "What is an IPO?"},
        {"role": "assistant", "content": "An IPO is a first public share sale."},
        {"role": "user", "content": "Explain that in simpler words"},
    ]
    ctx = _conversation_context(messages)
    assert "IPO" in ctx
    assert "simpler words" not in ctx

    model = _ScriptedModel(
        [
            AIMessage(content=""),
            AIMessage(content="An IPO is when a private company first sells shares publicly."),
            AIMessage(content="PASS"),
        ]
    )
    result = run_multi_agent_glossary(messages, model=model)
    assert result["mode"] == "multi_agent"
    assert "IPO" in result["assistant_message"] or "share" in result["assistant_message"].lower()


def test_critic_refuses_after_retry_exhausted(fixture_index: Path) -> None:
    from backend.glossary.agents.critic import critic_node

    out = critic_node(
        {
            "draft_answer": "You should buy this stock tomorrow for sure.",
            "evidence_pack": [{"term": "IPO", "excerpt": "ipo"}],
            "citations": [{"module": 1, "chapter": "IPO", "url": "https://example.com"}],
            "critic_retries": 1,
        }
    )
    assert out["critic_pass"] is True
    assert out.get("refusal", {}).get("category") == "insufficient_evidence"
    assert "grounded" in out["assistant_message"].lower() or "evidence" in out["assistant_message"].lower()
