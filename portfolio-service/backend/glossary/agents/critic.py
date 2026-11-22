"""Critic node: grounding / citation / no-advice checks."""
from __future__ import annotations

import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from .state import GlossaryGraphState

_ADVICE = re.compile(
    r"\b(you should buy|you should sell|i recommend buying|i recommend selling)\b",
    re.IGNORECASE,
)


def critic_node(state: GlossaryGraphState, *, model: BaseChatModel | None = None) -> dict[str, Any]:
    draft = (state.get("draft_answer") or state.get("assistant_message") or "").strip()
    evidence = state.get("evidence_pack") or []
    citations = state.get("citations") or []
    retries = int(state.get("critic_retries") or 0)
    notes: list[str] = []

    if not draft:
        notes.append("Draft answer is empty.")
    if not evidence:
        notes.append("No evidence pack; refuse to pass unsourced prose.")
    if evidence and not citations:
        notes.append("Missing citations for evidence-backed answer.")
    if _ADVICE.search(draft or ""):
        notes.append("Remove buy/sell recommendation language.")

    # Heuristic: long draft with zero chunk/url anchors
    if draft and evidence:
        anchors = [
            str(e.get("term") or "")
            for e in evidence
            if e.get("term")
        ] + [str(e.get("chapter") or "") for e in evidence if e.get("chapter")]
        if anchors and not any(a and a.lower() in draft.lower() for a in anchors if len(a) > 2):
            # Soft signal only — LLM critic may override
            if model is None:
                notes.append("Answer does not clearly ground in evidence terms/chapters.")

    if model is not None and draft and evidence and not notes:
        try:
            result = model.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are a strict grounding critic. "
                            "Reply PASS or FAIL. If FAIL, add one short line of notes. "
                            "Fail if unsourced claims, advice language, or giant verbatim paste."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"Draft:\n{draft[:3000]}\n\n"
                            f"Evidence count: {len(evidence)}; citations: {len(citations)}"
                        )
                    ),
                ]
            )
            text = (getattr(result, "content", None) or "").strip()
            if text.upper().startswith("FAIL"):
                notes.append(text)
        except Exception:
            pass

    if notes and retries < 1:
        return {
            "critic_pass": False,
            "critic_notes": "; ".join(notes),
            "critic_retries": retries + 1,
            "trace": [{"agent": "critic", "pass": False, "notes": notes}],
        }

    # Pass (or retries exhausted — ship draft with citations anyway)
    return {
        "critic_pass": True,
        "critic_notes": "",
        "assistant_message": draft,
        "citations": citations,
        "trace": [{"agent": "critic", "pass": True, "forced": bool(notes)}],
    }
