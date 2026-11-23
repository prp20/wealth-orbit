"""Answerer node: prose from EvidencePack only."""
from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from .state import GlossaryGraphState

# Model sometimes pastes retrieval ids like 【seed:IPO】 or [m1-c25] into prose.
_CITATION_MARKERS = re.compile(
    r"(?:【[^】]+】|\[[\w:.-]{1,40}\]|(?:\s*source\s*ids?\s*:.*$))",
    re.IGNORECASE | re.MULTILINE,
)
_MD_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)


def _coerce_content_text(content: Any) -> str:
    """LangChain content may be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content or "")


def answer_node(state: GlossaryGraphState, *, model: BaseChatModel) -> dict[str, Any]:
    user_text = state.get("user_text") or ""
    conversation_context = (state.get("conversation_context") or "").strip()
    evidence = state.get("evidence_pack") or []
    critic_notes = (state.get("critic_notes") or "").strip()

    if not evidence:
        msg = (
            "I could not find enough grounded glossary/corpus evidence for that question. "
            "Try a specific investing term, or run local Varsity ingest if the corpus is empty."
        )
        return {
            "draft_answer": msg,
            "assistant_message": msg,
            "citations": [],
            "trace": [{"agent": "answerer", "empty_evidence": True}],
        }

    pack_json = json.dumps(evidence, ensure_ascii=False)[:8000]
    notes = f"\nCritic notes to fix:\n{critic_notes}\n" if critic_notes else ""
    human = f"Question:\n{user_text}\n\nEvidence pack JSON:\n{pack_json}"
    if conversation_context:
        human = (
            f"Prior conversation:\n{conversation_context}\n\n"
            f"Current question:\n{user_text}\n\n"
            f"Evidence pack JSON:\n{pack_json}"
        )
    try:
        result = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are the Wealth Orbit glossary answerer. "
                        "Write a clear learner-friendly explanation using ONLY the evidence pack. "
                        "Do not invent facts. Do not give buy/sell advice. "
                        "Do not tell the user to go read a chapter instead of explaining. "
                        "Use prior conversation only to resolve pronouns/follow-ups. "
                        "Keep quotes short. You may name a Varsity chapter in plain words. "
                        "Format: short paragraphs; optional numbered steps. "
                        "Use **bold** for key terms only. "
                        "Do NOT use markdown headings (#). "
                        "Do NOT insert citation markers, chunk ids, brackets like 【…】 or [m1-c25], "
                        "or a 'Sources:' block — evidence is shown separately in the UI."
                        f"{notes}"
                    )
                ),
                HumanMessage(content=human),
            ]
        )
        draft = _clean_answer_prose(_coerce_content_text(getattr(result, "content", None)))
    except Exception:
        draft = ""
    if not draft:
        # Fallback: stitch seed excerpts
        parts = []
        for item in evidence[:4]:
            term = item.get("term")
            excerpt = item.get("excerpt") or ""
            if term:
                parts.append(f"**{term}** — {excerpt}")
            elif excerpt:
                parts.append(excerpt)
        draft = "\n\n".join(parts) or "No answer could be synthesized from evidence."

    citations = _citations_from_evidence(evidence)
    return {
        "draft_answer": draft,
        "assistant_message": draft,
        "citations": citations,
        "trace": [{"agent": "answerer", "citation_count": len(citations)}],
    }


def _clean_answer_prose(text: str) -> str:
    cleaned = _CITATION_MARKERS.sub("", text or "")
    cleaned = _MD_HEADING.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _citations_from_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe by module+chapter+url; prefer seed rows; cap for a clean evidence panel."""
    seen: set[tuple[Any, ...]] = set()
    citations: list[dict[str, Any]] = []

    def add(item: dict[str, Any]) -> None:
        excerpt = str(item.get("excerpt") or "")
        words = excerpt.split()
        if len(words) > 40:
            excerpt = " ".join(words[:40]) + "…"
        chapter = str(item.get("chapter") or "")
        url = str(item.get("url") or "")
        module = item.get("module") or 0
        # Collapse many chunks from the same chapter into one evidence row.
        key = (module, chapter.lower() or url)
        if not chapter and not url and not item.get("term"):
            return
        if key in seen:
            return
        seen.add(key)
        citations.append(
            {
                "module": module,
                "chapter": chapter,
                "url": url,
                "excerpt": excerpt,
                "chunk_id": item.get("chunk_id"),
                "term": item.get("term"),
            }
        )

    def _looks_noisy(excerpt: str) -> bool:
        # Mid-PDF accounting dumps make a poor evidence UI.
        if re.search(r"\d{3,}[,\d]*", excerpt or ""):
            digit_ratio = sum(ch.isdigit() for ch in excerpt) / max(len(excerpt), 1)
            if digit_ratio > 0.12:
                return True
        return False

    # Seed definitions first, then unique chapters from corpus hits.
    for item in evidence:
        if item.get("kind") == "seed" or str(item.get("chunk_id") or "").startswith("seed:"):
            add(item)
    for item in evidence:
        if _looks_noisy(str(item.get("excerpt") or "")):
            continue
        add(item)
    return citations[:3]
