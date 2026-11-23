"""Retriever node: ReAct-style tool loop over corpus + seed tools."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..tools import (
    execute_glossary_tool,
    parse_tool_arguments,
)
from .state import EvidenceItem, GlossaryGraphState

RETRIEVER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": "Hybrid search over local Varsity corpus chunks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chunk",
            "description": "Read a chunk by id.",
            "parameters": {
                "type": "object",
                "properties": {"chunk_id": {"type": "string"}},
                "required": ["chunk_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_glossary",
            "description": "Search curated glossary seed terms.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_glossary_term",
            "description": "Fetch one seed term definition.",
            "parameters": {
                "type": "object",
                "properties": {"term_or_alias": {"type": "string"}},
                "required": ["term_or_alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_chapter",
            "description": "Lookup chapter metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {"type": "integer"},
                    "chapter_title": {"type": "string"},
                },
                "required": ["module"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done_retrieving",
            "description": "Finish retrieval when evidence is enough.",
            "parameters": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
            },
        },
    },
]

MAX_ROUNDS = 5


def retrieve_node(state: GlossaryGraphState, *, model: BaseChatModel) -> dict[str, Any]:
    user_text = state.get("user_text") or ""
    conversation_context = (state.get("conversation_context") or "").strip()
    evidence: list[EvidenceItem] = list(state.get("evidence_pack") or [])
    tool_trace: list[dict[str, Any]] = []
    search_query = user_text
    if conversation_context:
        # Prefer the latest question but keep prior terms for follow-ups ("explain that").
        search_query = f"{user_text}\n\nPrior conversation:\n{conversation_context}"

    bound = model.bind_tools(RETRIEVER_TOOLS)
    human_bits = [f"Current question:\n{user_text}"]
    if conversation_context:
        human_bits.append(f"Prior conversation (for context only):\n{conversation_context}")
    messages: list[Any] = [
        SystemMessage(
            content=(
                "You gather evidence for a glossary answer. "
                "Use search_corpus and seed tools. Prefer short excerpts. "
                "Use prior conversation only to resolve follow-ups; search for the current question. "
                "Call done_retrieving when you have enough snippets. Max a few tool rounds."
            )
        ),
        HumanMessage(content="\n\n".join(human_bits)),
    ]

    done = False
    for _ in range(MAX_ROUNDS):
        if done:
            break
        ai: AIMessage = bound.invoke(messages)  # type: ignore[assignment]
        messages.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", "")
            if isinstance(args, str):
                args = parse_tool_arguments(args)
            if not isinstance(args, dict):
                args = {}
            result = execute_glossary_tool(str(name), args)
            tool_trace.append({"name": name, "arguments": args, "result": result})
            _absorb_evidence(evidence, name=str(name), result=result)
            messages.append(
                ToolMessage(content=json.dumps(result)[:4000], tool_call_id=str(call_id or name))
            )
            if name == "done_retrieving" or result.get("done"):
                done = True

    if not evidence:
        # Deterministic seed/corpus bootstrap when the model skips tools
        seed = execute_glossary_tool("search_glossary", {"query": user_text})
        tool_trace.append({"name": "search_glossary", "arguments": {"query": user_text}, "result": seed})
        for match in (seed.get("matches") or [])[:3]:
            term_payload = execute_glossary_tool(
                "get_glossary_term", {"term_or_alias": match.get("term", "")}
            )
            tool_trace.append(
                {
                    "name": "get_glossary_term",
                    "arguments": {"term_or_alias": match.get("term")},
                    "result": term_payload,
                }
            )
            _absorb_evidence(evidence, name="get_glossary_term", result=term_payload)
        corpus = execute_glossary_tool("search_corpus", {"query": search_query, "k": 5})
        tool_trace.append(
            {
                "name": "search_corpus",
                "arguments": {"query": search_query, "k": 5},
                "result": corpus,
            }
        )
        _absorb_evidence(evidence, name="search_corpus", result=corpus)

    return {
        "evidence_pack": evidence,
        "trace": [{"agent": "retriever", "tools": tool_trace, "evidence_count": len(evidence)}],
    }


def _absorb_evidence(pack: list[EvidenceItem], *, name: str, result: dict[str, Any]) -> None:
    if name == "search_corpus":
        for hit in result.get("hits") or []:
            if not isinstance(hit, dict):
                continue
            pack.append(
                {
                    "chunk_id": str(hit.get("chunk_id") or ""),
                    "module": hit.get("module"),
                    "chapter": hit.get("chapter"),
                    "url": hit.get("url"),
                    "excerpt": hit.get("excerpt"),
                    "term": hit.get("term"),
                    "kind": hit.get("kind"),
                }
            )
    elif name == "read_chunk" and result.get("found"):
        text = str(result.get("text") or "")
        excerpt = " ".join(text.split())
        if len(excerpt) > 280:
            excerpt = excerpt[:279] + "…"
        pack.append(
            {
                "chunk_id": str(result.get("chunk_id") or ""),
                "module": result.get("module"),
                "chapter": result.get("chapter"),
                "url": result.get("url"),
                "excerpt": excerpt,
                "term": result.get("term"),
                "kind": result.get("kind"),
            }
        )
    elif name == "get_glossary_term" and result.get("found"):
        sources = result.get("sources") or []
        source = sources[0] if sources else {}
        pack.append(
            {
                "chunk_id": f"seed:{result.get('term')}",
                "module": source.get("module"),
                "chapter": source.get("chapter"),
                "url": source.get("url"),
                "excerpt": str(result.get("definition") or "")[:280],
                "term": result.get("term"),
                "kind": "seed",
            }
        )
