"""Server-enforced glossary tool allowlist for the Groq agent."""
from __future__ import annotations

import json
from typing import Any

from .guards import REFUSAL_MESSAGES
from .matcher import GlossaryMatcher, normalize_phrase
from .models import GlossaryTerm, RefusalCategory

ALLOWED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "search_glossary",
        "get_glossary_term",
        "refuse_out_of_scope",
    }
)

GLOSSARY_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_glossary",
            "description": (
                "Search curated glossary seed terms by name, alias, or definition snippet. "
                "Returns ranked matches; use get_glossary_term for the full definition."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Term name, alias, or keywords to search for.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_glossary_term",
            "description": (
                "Fetch one glossary entry by canonical term or known alias, "
                "including definition and Varsity source links."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "term_or_alias": {
                        "type": "string",
                        "description": "Canonical term or alias from the seed glossary.",
                    },
                },
                "required": ["term_or_alias"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refuse_out_of_scope",
            "description": (
                "Refuse requests outside glossary scope: investment advice, "
                "buy/sell/switch picks, live prices, or bulk Varsity content dumps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief user-facing explanation of the refusal.",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["advice", "dump", "out_of_scope"],
                        "description": "Refusal category for telemetry and guardrails.",
                    },
                },
                "required": ["reason"],
            },
        },
    },
]


def _sources_payload(term: GlossaryTerm) -> list[dict[str, Any]]:
    return [
        {"module": source.module, "chapter": source.chapter, "url": source.url}
        for source in term.sources
    ]


def _resolve_term(term_or_alias: str, matcher: GlossaryMatcher) -> GlossaryTerm | None:
    direct = matcher.match(term_or_alias)
    if direct is not None:
        return direct
    lookup_key = normalize_phrase(term_or_alias)
    return matcher._lookup.get(lookup_key)


def _score_term(query: str, entry: GlossaryTerm) -> int:
    term_n = normalize_phrase(entry.term)
    if term_n == query:
        return 100
    score = 0
    if query in term_n or term_n in query:
        score = max(score, 80)
    for alias in entry.aliases:
        alias_n = normalize_phrase(alias)
        if alias_n == query:
            return 95
        if query in alias_n or alias_n in query:
            score = max(score, 75)
    definition_n = normalize_phrase(entry.definition)
    if query in definition_n:
        score = max(score, 45)
    return score


def search_glossary(
    query: str,
    *,
    matcher: GlossaryMatcher | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    """Rank seed terms matching query (name, alias, or definition keywords)."""
    cleaned = query.strip()
    if not cleaned:
        return {"query": query, "matches": []}
    normalized_query = normalize_phrase(cleaned)
    glossary_matcher = matcher or GlossaryMatcher()
    scored: list[tuple[int, GlossaryTerm]] = []
    for entry in glossary_matcher._terms:
        score = _score_term(normalized_query, entry)
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda item: (-item[0], item[1].term.lower()))
    matches = [
        {
            "term": entry.term,
            "score": score,
            "definition_preview": entry.definition[:160],
        }
        for score, entry in scored[:limit]
    ]
    return {"query": cleaned, "matches": matches}


def get_glossary_term(
    term_or_alias: str,
    *,
    matcher: GlossaryMatcher | None = None,
) -> dict[str, Any]:
    """Return one seed term definition and sources, or not_found."""
    glossary_matcher = matcher or GlossaryMatcher()
    entry = _resolve_term(term_or_alias, glossary_matcher)
    if entry is None:
        return {"found": False, "term_or_alias": term_or_alias}
    return {
        "found": True,
        "term": entry.term,
        "aliases": list(entry.aliases),
        "definition": entry.definition,
        "sources": _sources_payload(entry),
    }


def refuse_out_of_scope(reason: str, *, category: str = "out_of_scope") -> dict[str, Any]:
    """Structured refusal payload (advice, dump, or other out-of-scope)."""
    normalized = category.strip().lower()
    if normalized == RefusalCategory.ADVICE.value:
        template = REFUSAL_MESSAGES[RefusalCategory.ADVICE]
    elif normalized == RefusalCategory.DUMP.value:
        template = REFUSAL_MESSAGES[RefusalCategory.DUMP]
    else:
        template = reason.strip() or (
            "This assistant only explains investing terminology from the curated glossary."
        )
    return {
        "refused": True,
        "category": normalized,
        "reason": reason.strip() or template,
        "message": template,
    }


def execute_glossary_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    matcher: GlossaryMatcher | None = None,
) -> dict[str, Any]:
    """Dispatch a tool call; unknown names are rejected server-side."""
    if name not in ALLOWED_TOOL_NAMES:
        return {
            "error": "tool_not_allowed",
            "detail": f"Tool {name!r} is not in the glossary allowlist.",
        }
    if name == "search_glossary":
        return search_glossary(str(arguments.get("query", "")), matcher=matcher)
    if name == "get_glossary_term":
        return get_glossary_term(str(arguments.get("term_or_alias", "")), matcher=matcher)
    if name == "refuse_out_of_scope":
        return refuse_out_of_scope(
            str(arguments.get("reason", "")),
            category=str(arguments.get("category", "out_of_scope")),
        )
    return {"error": "unhandled_tool"}


def parse_tool_arguments(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = raw.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}