"""Answerer node: prose from EvidencePack only."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from .state import GlossaryGraphState


def answer_node(state: GlossaryGraphState, *, model: BaseChatModel) -> dict[str, Any]:
    user_text = state.get("user_text") or ""
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
    result = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are the Wealth Orbit glossary answerer. "
                    "Write a clear learner-friendly explanation using ONLY the evidence pack. "
                    "Do not invent facts. Do not give buy/sell advice. "
                    "Do not tell the user to go read a chapter instead of explaining. "
                    "Keep quotes short. Mention module/chapter naturally when helpful."
                    f"{notes}"
                )
            ),
            HumanMessage(
                content=f"Question:\n{user_text}\n\nEvidence pack JSON:\n{pack_json}"
            ),
        ]
    )
    draft = (getattr(result, "content", None) or "").strip()
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


def _citations_from_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    citations: list[dict[str, Any]] = []
    for item in evidence:
        excerpt = str(item.get("excerpt") or "")
        words = excerpt.split()
        if len(words) > 40:
            excerpt = " ".join(words[:40]) + "…"
        key = (
            item.get("module"),
            item.get("chapter"),
            item.get("url"),
            item.get("chunk_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "module": item.get("module") or 0,
                "chapter": item.get("chapter") or "",
                "url": item.get("url") or "",
                "excerpt": excerpt,
                "chunk_id": item.get("chunk_id"),
                "term": item.get("term"),
            }
        )
    return citations
