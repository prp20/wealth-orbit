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

_INSUFFICIENT_EVIDENCE = (
    "I could not produce a sufficiently grounded glossary answer from the available evidence. "
    "Try a more specific investing term, or rephrase the question."
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
            if isinstance(text, list):
                text = " ".join(str(part) for part in text)
            if str(text).upper().startswith("FAIL"):
                notes.append(str(text))
        except Exception:
            pass

    if notes and retries < 1:
        return {
            "critic_pass": False,
            "critic_notes": "; ".join(notes),
            "critic_retries": retries + 1,
            "trace": [{"agent": "critic", "pass": False, "notes": notes}],
        }

    if notes:
        # Exhausted retries with remaining issues — refuse instead of forced pass.
        return {
            "critic_pass": True,
            "critic_notes": "; ".join(notes),
            "assistant_message": _INSUFFICIENT_EVIDENCE,
            "draft_answer": _INSUFFICIENT_EVIDENCE,
            "citations": [],
            "refusal": {
                "category": "insufficient_evidence",
                "reason": _INSUFFICIENT_EVIDENCE,
            },
            "trace": [{"agent": "critic", "pass": False, "refused": True, "notes": notes}],
        }

    return {
        "critic_pass": True,
        "critic_notes": "",
        "assistant_message": draft,
        "citations": citations,
        "trace": [{"agent": "critic", "pass": True}],
    }
