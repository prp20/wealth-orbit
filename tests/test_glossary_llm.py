"""Model factory unit tests (no live API calls)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary import llm as glossary_llm  # noqa: E402


def test_provider_defaults_to_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLOSSARY_LLM_PROVIDER", raising=False)
    assert glossary_llm.glossary_llm_provider() == "groq"


def test_configured_requires_matching_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOSSARY_LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert glossary_llm.glossary_llm_configured() is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    assert glossary_llm.glossary_llm_configured() is True


def test_get_chat_model_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOSSARY_LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    monkeypatch.setenv("GLOSSARY_LLM_MODEL", "openai/gpt-oss-120b")

    class _FakeChatGroq:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr("langchain_groq.ChatGroq", _FakeChatGroq)
    model = glossary_llm.get_glossary_chat_model()
    assert isinstance(model, _FakeChatGroq)
    assert model.kwargs["model"] == "openai/gpt-oss-120b"


def test_openai_compatible_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLOSSARY_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GLOSSARY_LLM_BASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="GLOSSARY_LLM_BASE_URL"):
        glossary_llm.get_glossary_chat_model()
