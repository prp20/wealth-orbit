"""Compile and invoke Router → Retriever → Answerer → Critic graph."""
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.graph import END, START, StateGraph

from ..llm import get_glossary_chat_model, glossary_llm_configured
from ..rag.retrieve import index_ready
from .answerer import answer_node
from .critic import critic_node
from .retriever import retrieve_node
from .router import route_node
from .state import GlossaryGraphState

logger = logging.getLogger(__name__)


def _last_user_text(messages: list[dict[str, Any]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            text = item["content"].strip()
            if text:
                return text
    return ""


def _conversation_context(
    messages: list[dict[str, Any]],
    *,
    max_turns: int = 6,
    max_chars: int = 1600,
) -> str:
    """Prior user/assistant turns (excluding the latest user message) for multi-turn RAG."""
    prior: list[dict[str, Any]] = []
    seen_latest_user = False
    for item in reversed(messages):
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        if not seen_latest_user and role == "user":
            seen_latest_user = True
            continue
        prior.append({"role": role, "content": text})
        if len(prior) >= max_turns:
            break
    if not prior:
        return ""
    prior.reverse()
    lines = [f"{row['role']}: {row['content']}" for row in prior]
    blob = "\n".join(lines)
    if len(blob) > max_chars:
        blob = blob[-max_chars:]
    return blob


def build_glossary_graph(model: BaseChatModel):
    graph = StateGraph(GlossaryGraphState)

    def router(state: GlossaryGraphState) -> dict[str, Any]:
        return route_node(state, model=model)

    def retriever(state: GlossaryGraphState) -> dict[str, Any]:
        return retrieve_node(state, model=model)

    def answerer(state: GlossaryGraphState) -> dict[str, Any]:
        return answer_node(state, model=model)

    def critic(state: GlossaryGraphState) -> dict[str, Any]:
        return critic_node(state, model=model)

    def after_router(state: GlossaryGraphState) -> Literal["retriever", "__end__"]:
        if state.get("route") == "refuse":
            return END
        return "retriever"

    def after_critic(state: GlossaryGraphState) -> Literal["answerer", "__end__"]:
        if state.get("critic_pass"):
            return END
        return "answerer"

    graph.add_node("router", router)
    graph.add_node("retriever", retriever)
    graph.add_node("answerer", answerer)
    graph.add_node("critic", critic)

    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", after_router, {"retriever": "retriever", END: END})
    graph.add_edge("retriever", "answerer")
    graph.add_edge("answerer", "critic")
    graph.add_conditional_edges("critic", after_critic, {"answerer": "answerer", END: END})
    return graph.compile()


def multi_agent_available() -> bool:
    return glossary_llm_configured() and index_ready()


def run_multi_agent_glossary(
    messages: list[dict[str, Any]],
    *,
    model: BaseChatModel | None = None,
) -> dict[str, Any]:
    """Invoke the multi-agent pipeline. Caller should ensure LLM+index readiness."""
    chat_model = model or get_glossary_chat_model()
    user_text = _last_user_text(messages)
    conversation_context = _conversation_context(messages)
    app = build_glossary_graph(chat_model)
    final: GlossaryGraphState = app.invoke(
        {
            "messages": messages,
            "user_text": user_text,
            "conversation_context": conversation_context,
            "evidence_pack": [],
            "citations": [],
            "critic_retries": 0,
            "trace": [],
        }
    )

    # Keep internal graph trace off the public payload (sanitizer also strips it).
    payload: dict[str, Any] = {
        "assistant_message": final.get("assistant_message")
        or final.get("draft_answer")
        or "",
        "mode": "multi_agent",
    }
    if final.get("refusal"):
        payload["refusal"] = final["refusal"]
    citations = final.get("citations") or []
    if citations:
        payload["citations"] = citations
    return payload
