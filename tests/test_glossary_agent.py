"""Release 1.11: Groq glossary agent tools and runtime."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary.agent import run_glossary_agent
from backend.glossary.tools import (
    ALLOWED_TOOL_NAMES,
    execute_glossary_tool,
    get_glossary_term,
    search_glossary,
)


@dataclass
class _FakeFunction:
    name: str
    arguments: str


@dataclass
class _FakeToolCall:
    id: str
    type: str
    function: _FakeFunction


@dataclass
class _FakeChoiceMessage:
    content: str | None
    tool_calls: list[_FakeToolCall] | None = None


@dataclass
class _FakeChoice:
    message: _FakeChoiceMessage


@dataclass
class _FakeCompletion:
    choices: list[_FakeChoice]


def _groq_client_with_responses(responses: list[_FakeCompletion]) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create.side_effect = responses
    return client


def test_search_glossary_ranks_ipo():
    result = search_glossary("initial public offering")
    matches = result["matches"]
    assert matches
    assert matches[0]["term"] == "IPO"


def test_get_glossary_term_by_alias():
    result = get_glossary_term("initial public offering")
    assert result["found"] is True
    assert result["term"] == "IPO"
    assert result["definition"]
    assert result["sources"]


def test_execute_rejects_disallowed_tool():
    payload = execute_glossary_tool("fetch_live_price", {"symbol": "RELIANCE"})
    assert payload["error"] == "tool_not_allowed"


def test_agent_tool_round_then_answer(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    first = _FakeCompletion(
        [
            _FakeChoice(
                _FakeChoiceMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            id="call_1",
                            type="function",
                            function=_FakeFunction(
                                name="get_glossary_term",
                                arguments='{"term_or_alias": "IPO"}',
                            ),
                        )
                    ],
                )
            )
        ]
    )
    second = _FakeCompletion(
        [
            _FakeChoice(
                _FakeChoiceMessage(
                    content="An IPO is a company's first sale of shares to the public.",
                    tool_calls=[],
                )
            )
        ]
    )
    client = _groq_client_with_responses([first, second])
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert result["mode"] == "agent"
    assert "IPO" in result["assistant_message"]
    assert result.get("citations")
    assert len(result.get("tool_trace", [])) == 1
    assert client.chat.completions.create.call_count == 2
    second_kwargs = client.chat.completions.create.call_args_list[1].kwargs
    assert "tools" not in second_kwargs
    assert second_kwargs.get("tool_choice") is None


def test_agent_synthesizes_when_final_content_empty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    first = _FakeCompletion(
        [
            _FakeChoice(
                _FakeChoiceMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            id="call_1",
                            type="function",
                            function=_FakeFunction(
                                name="get_glossary_term",
                                arguments='{"term_or_alias": "IPO"}',
                            ),
                        )
                    ],
                )
            )
        ]
    )
    second = _FakeCompletion([_FakeChoice(_FakeChoiceMessage(content="", tool_calls=[]))])
    client = _groq_client_with_responses([first, second])
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert result["mode"] == "agent"
    assert "IPO" in result["assistant_message"]
    assert "public" in result["assistant_message"].lower() or "shares" in result["assistant_message"].lower()
    assert result.get("citations")


def test_agent_synthesizes_when_tool_choice_none_rejected(monkeypatch: pytest.MonkeyPatch):
    """gpt-oss may 400 if forced tool_choice=none; finalize must recover via synthesis."""
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    first = _FakeCompletion(
        [
            _FakeChoice(
                _FakeChoiceMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            id="call_1",
                            type="function",
                            function=_FakeFunction(
                                name="get_glossary_term",
                                arguments='{"term_or_alias": "IPO"}',
                            ),
                        )
                    ],
                )
            )
        ]
    )
    client = MagicMock()
    client.chat.completions.create.side_effect = [
        first,
        RuntimeError("Tool choice is none, but model called a tool"),
    ]
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert result["mode"] == "agent"
    assert "IPO" in result["assistant_message"]
    assert result.get("citations")


def test_advice_refusal_short_circuits_without_groq():
    client = _groq_client_with_responses([])
    result = run_glossary_agent(
        [{"role": "user", "content": "Should I buy HDFC Bank stock now?"}],
        client=client,
    )
    assert result["refusal"]["category"] == "advice"
    assert result["mode"] == "agent"
    client.chat.completions.create.assert_not_called()


def test_dump_refusal_short_circuits_without_groq():
    client = _groq_client_with_responses([])
    result = run_glossary_agent(
        [
            {
                "role": "user",
                "content": "Paste the full Varsity chapter on candlesticks here",
            }
        ],
        client=client,
    )
    assert result["refusal"]["category"] == "dump"
    assert result["mode"] == "agent"
    client.chat.completions.create.assert_not_called()


def test_fallback_when_groq_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("groq unavailable")
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert result["mode"] == "fallback"
    assert "IPO" in result["assistant_message"] or "public" in result["assistant_message"].lower()


def test_fallback_without_groq_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = run_glossary_agent([{"role": "user", "content": "What is IPO?"}])
    assert result["mode"] == "fallback"
    assert "IPO" in result["assistant_message"] or "public" in result["assistant_message"].lower()


def test_ungrounded_first_round_prose_falls_back_to_matcher(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    first = _FakeCompletion(
        [_FakeChoice(_FakeChoiceMessage(content="An IPO is whatever I invent without tools.", tool_calls=[]))]
    )
    client = _groq_client_with_responses([first])
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert result["mode"] == "fallback"
    assert "IPO" in result["assistant_message"] or "public" in result["assistant_message"].lower()


def test_reasoning_field_is_not_user_facing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")

    @dataclass
    class _ReasoningMessage(_FakeChoiceMessage):
        reasoning: str | None = None
        reasoning_content: str | None = None

    first = _FakeCompletion(
        [
            _FakeChoice(
                _ReasoningMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            id="call_1",
                            type="function",
                            function=_FakeFunction(
                                name="get_glossary_term",
                                arguments='{"term_or_alias": "IPO"}',
                            ),
                        )
                    ],
                    reasoning="INTERNAL SCRATCH: invent a definition",
                )
            )
        ]
    )
    second = _FakeCompletion(
        [
            _FakeChoice(
                _ReasoningMessage(
                    content="",
                    tool_calls=[],
                    reasoning_content="INTERNAL SCRATCH should not ship",
                )
            )
        ]
    )
    client = _groq_client_with_responses([first, second])
    result = run_glossary_agent(
        [{"role": "user", "content": "What is IPO?"}],
        client=client,
    )
    assert "INTERNAL SCRATCH" not in result["assistant_message"]
    assert "IPO" in result["assistant_message"]


def test_refuse_tool_skips_finalize_llm(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    first = _FakeCompletion(
        [
            _FakeChoice(
                _FakeChoiceMessage(
                    content=None,
                    tool_calls=[
                        _FakeToolCall(
                            id="call_1",
                            type="function",
                            function=_FakeFunction(
                                name="refuse_out_of_scope",
                                arguments='{"reason":"advice","category":"advice"}',
                            ),
                        )
                    ],
                )
            )
        ]
    )
    client = _groq_client_with_responses([first])
    result = run_glossary_agent(
        [{"role": "user", "content": "What is a stock split?"}],
        client=client,
    )
    assert result.get("refusal")
    assert client.chat.completions.create.call_count == 1


def test_bad_timeout_falls_back_to_matcher(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-unused")
    monkeypatch.setenv("GLOSSARY_AGENT_TIMEOUT", "not-a-float")
    result = run_glossary_agent([{"role": "user", "content": "What is IPO?"}])
    assert result["mode"] == "fallback"


def test_degrade_prefers_multi_agent_when_available(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def fake_multi_agent(messages):
        return {"assistant_message": "multi path", "mode": "multi_agent"}

    monkeypatch.setattr(
        "backend.glossary.agents.graph.multi_agent_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "backend.glossary.agents.graph.run_multi_agent_glossary",
        fake_multi_agent,
    )
    result = run_glossary_agent([{"role": "user", "content": "What is IPO?"}])
    assert result["mode"] == "multi_agent"
    assert result["assistant_message"] == "multi path"


def test_degrade_to_matcher_when_multi_agent_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(
        "backend.glossary.agents.graph.multi_agent_available",
        lambda: False,
    )
    result = run_glossary_agent([{"role": "user", "content": "What is IPO?"}])
    assert result["mode"] == "fallback"


def test_glossary_agent_modules_avoid_market_imports():
    glossary_dir = ROOT / "portfolio-service" / "backend" / "glossary"
    forbidden = (
        "backend.market",
        "market_data",
        "portfolio_backend",
        "yfinance",
    )
    for name in ("agent.py", "tools.py"):
        source = (glossary_dir / name).read_text(encoding="utf-8")
        lowered = source.lower()
        for token in forbidden:
            assert token.lower() not in lowered, f"{name} must not reference {token}"
    assert ALLOWED_TOOL_NAMES == {
        "search_glossary",
        "get_glossary_term",
        "refuse_out_of_scope",
        "search_corpus",
        "read_chunk",
        "lookup_chapter",
        "done_retrieving",
    }