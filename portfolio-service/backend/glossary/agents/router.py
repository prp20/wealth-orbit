"""Router node: heuristic refusal + optional LLM classify."""
from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from ..guards import REFUSAL_MESSAGES, detect_refusal
from ..models import RefusalCategory
from .state import GlossaryGraphState


def route_node(state: GlossaryGraphState, *, model: BaseChatModel | None = None) -> dict[str, Any]:
    user_text = (state.get("user_text") or "").strip()
    category = detect_refusal(user_text)
    if category is not None:
        reason = REFUSAL_MESSAGES[category]
        return {
            "route": "refuse",
            "refusal": {"category": category.value, "reason": reason},
            "assistant_message": reason,
            "trace": [{"agent": "router", "route": "refuse", "category": category.value}],
        }

    # Optional LLM classify for ambiguous portfolio / dump-adjacent asks
    if model is not None and _maybe_ambiguous(user_text):
        try:
            result = model.invoke(
                [
                    SystemMessage(
                        content=(
                            "Classify the user message for a glossary assistant. "
                            "Reply with exactly one token: glossary | refuse_advice | refuse_dump | refuse_other. "
                            "Refuse buy/sell/personalized advice, full PDF/chapter dumps, and live portfolio/price asks."
                        )
                    ),
                    HumanMessage(content=user_text),
                ]
            )
            token = (getattr(result, "content", None) or "").strip().lower()
            if "refuse_advice" in token:
                reason = REFUSAL_MESSAGES[RefusalCategory.ADVICE]
                return {
                    "route": "refuse",
                    "refusal": {"category": "advice", "reason": reason},
                    "assistant_message": reason,
                    "trace": [{"agent": "router", "route": "refuse", "category": "advice", "via": "llm"}],
                }
            if "refuse_dump" in token:
                reason = REFUSAL_MESSAGES[RefusalCategory.DUMP]
                return {
                    "route": "refuse",
                    "refusal": {"category": "dump", "reason": reason},
                    "assistant_message": reason,
                    "trace": [{"agent": "router", "route": "refuse", "category": "dump", "via": "llm"}],
                }
            if token.startswith("refuse"):
                reason = (
                    "This assistant only explains investing terminology from the curated glossary "
                    "and local Varsity corpus."
                )
                return {
                    "route": "refuse",
                    "refusal": {"category": "out_of_scope", "reason": reason},
                    "assistant_message": reason,
                    "trace": [{"agent": "router", "route": "refuse", "category": "out_of_scope", "via": "llm"}],
                }
        except Exception:
            pass

    return {
        "route": "glossary",
        "refusal": None,
        "trace": [{"agent": "router", "route": "glossary"}],
    }


def _maybe_ambiguous(text: str) -> bool:
    lower = text.lower()
    markers = ("portfolio", "my holdings", "price of", "live quote", "paste", "whole module", "pdf")
    return any(m in lower for m in markers)
