"""Sanitize glossary agent payloads for public HTTP responses."""
from __future__ import annotations

from typing import Any

# Keep public excerpts short so clients cannot harvest long corpus passages.
_MAX_EXCERPT_CHARS = 220
_MAX_EXCERPT_WORDS = 40


def _cap_excerpt(text: str | None) -> str | None:
    if text is None:
        return None
    raw = " ".join(str(text).split())
    if not raw:
        return None
    words = raw.split()
    if len(words) > _MAX_EXCERPT_WORDS:
        raw = " ".join(words[:_MAX_EXCERPT_WORDS]) + "…"
    if len(raw) > _MAX_EXCERPT_CHARS:
        raw = raw[: _MAX_EXCERPT_CHARS - 1] + "…"
    return raw


def sanitize_public_agent_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Strip internal traces and bound citation excerpts for unauthenticated clients.

    Keeps assistant_message, mode, refusal, and short citation metadata/excerpts.
    """
    out: dict[str, Any] = {
        "assistant_message": str(payload.get("assistant_message") or ""),
        "mode": payload.get("mode") or "fallback",
    }
    if payload.get("refusal"):
        out["refusal"] = payload["refusal"]

    citations = payload.get("citations")
    if isinstance(citations, list) and citations:
        cleaned: list[dict[str, Any]] = []
        for item in citations:
            if not isinstance(item, dict):
                continue
            row: dict[str, Any] = {
                "module": item.get("module") or 0,
                "chapter": item.get("chapter") or "",
                "url": item.get("url") or "",
            }
            if item.get("term"):
                row["term"] = item.get("term")
            excerpt = _cap_excerpt(item.get("excerpt"))
            if excerpt:
                row["excerpt"] = excerpt
            # Intentionally omit chunk_id — internal corpus pointer.
            cleaned.append(row)
        if cleaned:
            out["citations"] = cleaned
    return out
