"""Shared LangGraph state for glossary multi-agent POC."""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class EvidenceItem(TypedDict, total=False):
    chunk_id: str
    module: int | None
    chapter: str | None
    url: str | None
    excerpt: str | None
    term: str | None
    kind: str | None


class GlossaryGraphState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    user_text: str
    conversation_context: str
    route: Literal["glossary", "refuse"]
    refusal: dict[str, Any] | None
    evidence_pack: list[EvidenceItem]
    draft_answer: str
    citations: list[dict[str, Any]]
    critic_notes: str
    critic_pass: bool
    critic_retries: int
    assistant_message: str
    trace: Annotated[list[dict[str, Any]], operator.add]
