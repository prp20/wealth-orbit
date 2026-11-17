"""Groq tool-calling runtime for glossary chat (seed-only, allowlisted tools)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from groq import Groq

from .engine import answer_glossary_message
from .guards import REFUSAL_MESSAGES, detect_refusal
from .matcher import GlossaryMatcher
from .models import GlossaryResult, GlossaryResultKind, RefusalCategory
from .tools import (
    GLOSSARY_TOOL_SCHEMAS,
    execute_glossary_tool,
    parse_tool_arguments,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Wealth Orbit glossary assistant.

Scope: explain investing terminology only, using glossary seed tools for facts.

Rules:
- Call search_glossary or get_glossary_term before stating definitions.
- Do not invent definitions, prices, portfolio numbers, or Varsity chapter text.
- For buy/sell/switch advice, personalized recommendations, or bulk Varsity dump requests,
  call refuse_out_of_scope with a clear reason.
- Answer in clear prose; you may reference Varsity chapter URLs returned by tools.
"""

MAX_TOOL_ROUNDS = 6
DEFAULT_MODEL = "openai/gpt-oss-120b"
DEFAULT_TIMEOUT_SECONDS = 45.0


def _last_user_message(messages: list[dict[str, Any]]) -> str | None:
    for item in reversed(messages):
        if item.get("role") == "user":
            content = item.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return None


def _collect_citations(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, str, str]] = set()
    citations: list[dict[str, Any]] = []
    for entry in tool_trace:
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        sources = result.get("sources")
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            key = (
                int(source.get("module", 0)),
                str(source.get("chapter", "")),
                str(source.get("url", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "module": key[0],
                    "chapter": key[1],
                    "url": key[2],
                    "term": result.get("term"),
                }
            )
    return citations


def _refusal_from_tool_trace(tool_trace: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in reversed(tool_trace):
        if entry.get("name") != "refuse_out_of_scope":
            continue
        result = entry.get("result")
        if isinstance(result, dict) and result.get("refused"):
            return {
                "category": result.get("category"),
                "reason": result.get("message") or result.get("reason"),
            }
    return None


def _found_term_payloads(tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in tool_trace:
        if entry.get("name") != "get_glossary_term":
            continue
        result = entry.get("result")
        if not isinstance(result, dict) or not result.get("found"):
            continue
        term = str(result.get("term") or "")
        if not term or term in seen:
            continue
        seen.add(term)
        found.append(result)
    return found


def _tool_facts_ready(tool_trace: list[dict[str, Any]]) -> bool:
    """True when the model has enough seed facts to answer without more tools."""
    if _refusal_from_tool_trace(tool_trace) is not None:
        return True
    return bool(_found_term_payloads(tool_trace))


def _message_text(choice_message: Any) -> str:
    """Extract visible assistant text (gpt-oss may leave content empty)."""
    content = getattr(choice_message, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    for attr in ("reasoning", "reasoning_content"):
        value = getattr(choice_message, attr, None)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _synthesize_from_tool_trace(tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a prose reply from tool results when the model never emits final content."""
    refusal = _refusal_from_tool_trace(tool_trace)
    if refusal is not None:
        return {
            "assistant_message": str(refusal.get("reason") or ""),
            "mode": "agent",
            "refusal": refusal,
            "tool_trace": tool_trace,
        }

    found = _found_term_payloads(tool_trace)
    if found:
        parts = [f"**{item['term']}** — {item.get('definition') or ''}".strip() for item in found]
        payload: dict[str, Any] = {
            "assistant_message": "\n\n".join(parts),
            "mode": "agent",
            "tool_trace": tool_trace,
        }
        citations = _collect_citations(tool_trace)
        if citations:
            payload["citations"] = citations
        return payload

    for entry in reversed(tool_trace):
        if entry.get("name") != "search_glossary":
            continue
        result = entry.get("result")
        if not isinstance(result, dict):
            continue
        matches = result.get("matches") or []
        if not matches:
            continue
        lines = [
            f"- **{m.get('term')}**: {m.get('definition_preview') or ''}".strip()
            for m in matches[:5]
            if isinstance(m, dict)
        ]
        return {
            "assistant_message": "Here are related glossary terms:\n" + "\n".join(lines),
            "mode": "agent",
            "tool_trace": tool_trace,
        }

    return {
        "assistant_message": (
            "I looked in the glossary seed but could not finish a clear answer. "
            "Try asking for one term by name."
        ),
        "mode": "agent",
        "tool_trace": tool_trace,
    }


def _assistant_payload_from_fallback(result: GlossaryResult) -> dict[str, Any]:
    if result.kind is GlossaryResultKind.REFUSAL:
        return {
            "assistant_message": result.refusal_reason or "",
            "mode": "fallback",
            "refusal": {
                "category": result.refusal_category.value if result.refusal_category else None,
                "reason": result.refusal_reason,
            },
        }
    if result.kind is GlossaryResultKind.MATCH:
        citations = [
            {"module": s.module, "chapter": s.chapter, "url": s.url, "term": result.term}
            for s in result.sources
        ]
        body = result.definition or ""
        if result.term:
            body = f"**{result.term}** — {body}"
        return {
            "assistant_message": body,
            "mode": "fallback",
            "citations": citations,
        }
    return {
        "assistant_message": (
            "I could not find that term in the curated glossary seed. "
            "Try the exact term name or a shorter keyword."
        ),
        "mode": "fallback",
    }


def _precheck_refusal(user_text: str, category: RefusalCategory) -> dict[str, Any]:
    reason = REFUSAL_MESSAGES[category]
    tool_trace = [
        {
            "name": "refuse_out_of_scope",
            "arguments": {"reason": reason, "category": category.value},
            "result": {
                "refused": True,
                "category": category.value,
                "reason": reason,
                "message": reason,
            },
        }
    ]
    return {
        "assistant_message": reason,
        "mode": "agent",
        "refusal": {"category": category.value, "reason": reason},
        "tool_trace": tool_trace,
    }


def _build_completion_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seeded: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in messages:
        role = item.get("role")
        if role not in {"user", "assistant", "tool"}:
            continue
        payload: dict[str, Any] = {"role": role}
        if "content" in item:
            payload["content"] = item.get("content")
        if role == "assistant" and item.get("tool_calls"):
            payload["tool_calls"] = item["tool_calls"]
        if role == "tool":
            if item.get("tool_call_id"):
                payload["tool_call_id"] = item["tool_call_id"]
            if item.get("name"):
                payload["name"] = item["name"]
        seeded.append(payload)
    return seeded


def _payload_from_prose(text: str, tool_trace: list[dict[str, Any]]) -> dict[str, Any]:
    refusal = _refusal_from_tool_trace(tool_trace)
    citations = _collect_citations(tool_trace)
    payload: dict[str, Any] = {
        "assistant_message": text,
        "mode": "agent",
    }
    if citations:
        payload["citations"] = citations
    if tool_trace:
        payload["tool_trace"] = tool_trace
    if refusal:
        payload["refusal"] = refusal
    return payload


def _finalize_after_tools(
    *,
    client: Groq,
    model: str,
    timeout: float,
    chat_messages: list[dict[str, Any]],
    tool_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Produce the user-facing answer after seed tools ran.

    Do not use tool_choice=none — gpt-oss on Groq still emits tool calls and returns 400.
    Try one tool-free completion for prose; otherwise synthesize from tool results.
    """
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                *chat_messages,
                {
                    "role": "user",
                    "content": (
                        "Using only the glossary tool results already provided, "
                        "write a clear final answer for the user. Do not call any tools."
                    ),
                },
            ],
            timeout=timeout,
        )
        text = _message_text(completion.choices[0].message)
        if text:
            return _payload_from_prose(text, tool_trace)
    except Exception as exc:
        logger.info(
            "Glossary final prose pass failed (%s); synthesizing from tools",
            type(exc).__name__,
        )
    return _synthesize_from_tool_trace(tool_trace)


def _run_agent_loop(
    messages: list[dict[str, Any]],
    *,
    client: Groq,
    model: str,
    timeout: float,
) -> dict[str, Any]:
    chat_messages = _build_completion_messages(messages)
    matcher = GlossaryMatcher()
    tool_trace: list[dict[str, Any]] = []

    for _ in range(MAX_TOOL_ROUNDS):
        completion = client.chat.completions.create(
            model=model,
            messages=chat_messages,
            tools=GLOSSARY_TOOL_SCHEMAS,
            tool_choice="auto",
            timeout=timeout,
        )
        choice = completion.choices[0].message
        text = _message_text(choice)
        assistant_record: dict[str, Any] = {
            "role": "assistant",
            "content": text or (choice.content or ""),
        }
        tool_calls = list(choice.tool_calls or [])
        if tool_calls:
            assistant_record["tool_calls"] = [
                {
                    "id": call.id,
                    "type": call.type,
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in tool_calls
            ]
        chat_messages.append(assistant_record)

        if not tool_calls:
            if tool_trace and not text:
                return _synthesize_from_tool_trace(tool_trace)
            if tool_trace:
                return _payload_from_prose(
                    text
                    or "I could not generate a glossary answer. Please rephrase your question.",
                    tool_trace,
                )
            return {
                "assistant_message": text
                or "I could not generate a glossary answer. Please rephrase your question.",
                "mode": "agent",
            }

        for call in tool_calls:
            name = call.function.name
            arguments = parse_tool_arguments(call.function.arguments)
            result = execute_glossary_tool(name, arguments, matcher=matcher)
            tool_trace.append({"name": name, "arguments": arguments, "result": result})
            chat_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": name,
                    "content": json.dumps(result),
                }
            )

        if _tool_facts_ready(tool_trace):
            return _finalize_after_tools(
                client=client,
                model=model,
                timeout=timeout,
                chat_messages=chat_messages,
                tool_trace=tool_trace,
            )

    logger.warning("Glossary agent exceeded max tool rounds (%s); synthesizing from tools", MAX_TOOL_ROUNDS)
    if tool_trace:
        return _synthesize_from_tool_trace(tool_trace)
    raise RuntimeError("glossary_agent_max_tool_rounds")


def run_glossary_agent(
    messages: list[dict[str, Any]],
    *,
    client: Groq | None = None,
) -> dict[str, Any]:
    """
    Run multi-turn glossary agent chat.

    Returns assistant_message, optional citations/tool_trace, mode (agent|fallback),
    and optional refusal metadata.
    """
    if not messages:
        return {
            "assistant_message": "Ask a glossary question to get started.",
            "mode": "fallback",
        }

    user_text = _last_user_message(messages)
    if user_text:
        precheck = detect_refusal(user_text)
        if precheck is not None:
            return _precheck_refusal(user_text, precheck)

    api_key = os.environ.get("GROQ_API_KEY")
    if client is None and not api_key:
        fallback = answer_glossary_message(user_text or "")
        return _assistant_payload_from_fallback(fallback)

    model = os.environ.get("GLOSSARY_LLM_MODEL", DEFAULT_MODEL)
    timeout = float(os.environ.get("GLOSSARY_AGENT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS)))
    groq_client = client or Groq(api_key=api_key)

    try:
        return _run_agent_loop(messages, client=groq_client, model=model, timeout=timeout)
    except Exception:
        logger.exception("Glossary Groq agent failed; falling back to deterministic matcher")
        fallback = answer_glossary_message(user_text or "")
        return _assistant_payload_from_fallback(fallback)