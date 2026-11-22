"""Server-enforced glossary tool allowlist for the Groq agent."""
from __future__ import annotations

import json
from typing import Any

from .guards import REFUSAL_MESSAGES
from .matcher import GlossaryMatcher, normalize_phrase
from .models import GlossaryTerm, RefusalCategory

SEED_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "search_glossary",
        "get_glossary_term",
        "refuse_out_of_scope",
    }
)

CORPUS_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "search_corpus",
        "read_chunk",
        "lookup_chapter",
        "done_retrieving",
    }
)

ALLOWED_TOOL_NAMES: frozenset[str] = SEED_TOOL_NAMES | CORPUS_TOOL_NAMES

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
    {
        "type": "function",
        "function": {
            "name": "search_corpus",
            "description": (
                "Hybrid search over the local Varsity PDF-derived corpus. "
                "Returns chunk ids, scores, module/chapter/url, and short excerpts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "k": {
                        "type": "integer",
                        "description": "Max hits (default 5, max 12).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_chunk",
            "description": "Read one corpus chunk by id (capped length).",
            "parameters": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string", "description": "Chunk id from search_corpus."},
                },
                "required": ["chunk_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_chapter",
            "description": "Lookup Varsity chapter metadata from chapter_index.json.",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {"type": "integer", "description": "Varsity module number."},
                    "chapter_title": {
                        "type": "string",
                        "description": "Optional chapter title substring.",
                    },
                },
                "required": ["module"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "done_retrieving",
            "description": "Signal that enough evidence was gathered for answering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Brief note on what evidence was collected.",
                    },
                },
                "required": ["summary"],
            },
        },
    },
]

SEED_TOOL_SCHEMAS: list[dict[str, Any]] = [
    schema
    for schema in GLOSSARY_TOOL_SCHEMAS
    if schema.get("function", {}).get("name") in SEED_TOOL_NAMES
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


def search_corpus(query: str, *, k: int = 5) -> dict[str, Any]:
    from .rag.retrieve import hybrid_search, index_ready

    if not index_ready():
        return {
            "query": query,
            "hits": [],
            "error": "corpus_not_built",
            "detail": "Run the Varsity ingest CLI to build the local RAG index.",
        }
    hits = hybrid_search(query, k=k)
    slim = [
        {
            "chunk_id": h["chunk_id"],
            "score": h["score"],
            "module": h.get("module"),
            "chapter": h.get("chapter"),
            "url": h.get("url"),
            "excerpt": h.get("excerpt"),
            "kind": h.get("kind"),
            "term": h.get("term"),
        }
        for h in hits
    ]
    return {"query": query, "hits": slim}


def read_chunk_tool(chunk_id: str) -> dict[str, Any]:
    from .rag.retrieve import read_chunk

    hit = read_chunk(chunk_id)
    if hit is None:
        return {"found": False, "chunk_id": chunk_id}
    return {
        "found": True,
        "chunk_id": chunk_id,
        "module": hit.get("module"),
        "chapter": hit.get("chapter"),
        "url": hit.get("url"),
        "text": hit.get("text"),
        "kind": hit.get("kind"),
        "term": hit.get("term"),
    }


def lookup_chapter(module: int, chapter_title: str | None = None) -> dict[str, Any]:
    import json

    from .paths import chapter_index_path

    path = chapter_index_path()
    if not path.exists():
        return {"found": False, "detail": "chapter_index.json missing"}
    data = json.loads(path.read_text(encoding="utf-8"))
    modules = data.get("modules") or []
    match_mod = next((m for m in modules if int(m.get("module") or -1) == int(module)), None)
    if match_mod is None:
        return {"found": False, "module": module}
    chapters = match_mod.get("chapters") or []
    if chapter_title:
        needle = chapter_title.strip().lower()
        for chapter in chapters:
            title = str(chapter.get("title") or "")
            if needle in title.lower():
                return {
                    "found": True,
                    "module": module,
                    "module_title": match_mod.get("title"),
                    "chapter": title,
                    "url": chapter.get("url"),
                    "blurb": chapter.get("blurb"),
                }
    return {
        "found": True,
        "module": module,
        "module_title": match_mod.get("title"),
        "module_url": match_mod.get("url"),
        "chapters": [
            {"title": c.get("title"), "url": c.get("url"), "blurb": c.get("blurb")}
            for c in chapters[:12]
        ],
    }


def done_retrieving(summary: str) -> dict[str, Any]:
    return {"done": True, "summary": summary.strip()}


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
    if name == "search_corpus":
        k_raw = arguments.get("k", 5)
        try:
            k = int(k_raw)
        except (TypeError, ValueError):
            k = 5
        return search_corpus(str(arguments.get("query", "")), k=k)
    if name == "read_chunk":
        return read_chunk_tool(str(arguments.get("chunk_id", "")))
    if name == "lookup_chapter":
        try:
            module = int(arguments.get("module", 0))
        except (TypeError, ValueError):
            module = 0
        title = arguments.get("chapter_title")
        return lookup_chapter(module, str(title) if title else None)
    if name == "done_retrieving":
        return done_retrieving(str(arguments.get("summary", "")))
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