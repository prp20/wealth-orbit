"""Glossary chat engine: guards then seed retrieval (no LLM)."""
from __future__ import annotations

from .guards import REFUSAL_MESSAGES, detect_refusal
from .matcher import GlossaryMatcher
from .models import GlossaryResult, GlossaryResultKind


def answer_glossary_message(
    message: str,
    matcher: GlossaryMatcher | None = None,
) -> GlossaryResult:
    refusal = detect_refusal(message)
    if refusal is not None:
        return GlossaryResult(
            kind=GlossaryResultKind.REFUSAL,
            refusal_reason=REFUSAL_MESSAGES[refusal],
            refusal_category=refusal,
        )
    glossary = matcher or GlossaryMatcher()
    return glossary.to_result(message)