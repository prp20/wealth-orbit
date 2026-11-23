"""Model-agnostic chat model factory for glossary agents."""
from __future__ import annotations

import os
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

Provider = Literal["groq", "openai", "openai_compatible"]

DEFAULT_PROVIDER: Provider = "groq"
# Proven on Groq free/dev; override via GLOSSARY_LLM_MODEL (e.g. llama-3.3-70b-versatile).
DEFAULT_MODEL = "openai/gpt-oss-120b"


def glossary_llm_provider() -> Provider:
    raw = (os.getenv("GLOSSARY_LLM_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if raw in {"groq", "openai", "openai_compatible"}:
        return raw  # type: ignore[return-value]
    return DEFAULT_PROVIDER


def glossary_llm_model() -> str:
    return (os.getenv("GLOSSARY_LLM_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def glossary_llm_configured() -> bool:
    """True when the selected provider has a usable API key."""
    provider = glossary_llm_provider()
    if provider == "groq":
        return bool((os.getenv("GROQ_API_KEY") or "").strip())
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def get_glossary_chat_model(*, temperature: float = 0.2) -> BaseChatModel:
    """Build a LangChain chat model from env. Raises if the provider key is missing."""
    provider = glossary_llm_provider()
    model = glossary_llm_model()

    if provider == "groq":
        api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is required when GLOSSARY_LLM_PROVIDER=groq")
        from langchain_groq import ChatGroq

        return ChatGroq(model=model, api_key=api_key, temperature=temperature)

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required when GLOSSARY_LLM_PROVIDER is openai or openai_compatible"
        )
    from langchain_openai import ChatOpenAI

    kwargs: dict = {
        "model": model,
        "api_key": api_key,
        "temperature": temperature,
    }
    if provider == "openai_compatible":
        base_url = (os.getenv("GLOSSARY_LLM_BASE_URL") or "").strip()
        if not base_url:
            raise RuntimeError(
                "GLOSSARY_LLM_BASE_URL is required when GLOSSARY_LLM_PROVIDER=openai_compatible"
            )
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)
