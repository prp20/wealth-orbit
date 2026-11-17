"""Intent guards: refuse advice and Varsity dump/redistribution requests."""
from __future__ import annotations

import re

from .models import RefusalCategory

_ADVICE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(should|ought)\s+i\s+(buy|sell|switch|invest|hold|exit)\b",
        r"\bwhich\s+(stock|share|fund|scheme|mutual\s+fund)\s+should\s+i\b",
        r"\b(buy|sell|switch)\s+(this|that|it|now|today)\b",
        r"\brecommend(?:ation)?\s+(me|a|some)\b",
        r"\b(recommend|advise)\b.+\b(buy|sell|switch)\b",
        r"\b(buy|sell|switch)\b.+\b(recommend|advice)\b",
        r"\bpersonal(?:ized)?\s+advice\b",
        r"\bwhat\s+should\s+i\s+(buy|sell|invest\s+in)\b",
    )
)

_DUMP_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bfull\s+chapter\b",
        r"\bentire\s+chapter\b",
        r"\bvarsity\s+pdf\b",
        r"\bpdf\s+text\b",
        r"\bpaste\b.+\bvarsity\b",
        r"\bfull\s+varsity\s+chapter\b",
        r"\bdump\s+(all\s+)?(the\s+)?(definitions|glossary|terms)\b",
        r"\b(all|every)\s+(glossary\s+)?definitions\b",
        r"\bwholesale\b.+\b(definitions|varsity|glossary)\b",
        r"\b(definitions|varsity|glossary)\b.+\bwholesale\b",
        r"\bredistribute\b",
        r"\bcopy\s+(paste\s+)?(the\s+)?varsity\b",
        r"\bvarsity\s+(full\s+)?text\b",
        r"\bdownload\s+(all\s+)?varsity\b",
        r"\bexport\s+(all\s+)?(definitions|terms)\b",
    )
)

REFUSAL_MESSAGES: dict[RefusalCategory, str] = {
    RefusalCategory.ADVICE: (
        "This glossary explains investing terms only. "
        "It cannot give buy, sell, switch, or personalized investment advice."
    ),
    RefusalCategory.DUMP: (
        "I can share short curated definitions with Varsity chapter links for further reading, "
        "not full chapter text, PDFs, or bulk copies of Varsity content."
    ),
}


def detect_refusal(message: str) -> RefusalCategory | None:
    text = message.strip()
    if not text:
        return None
    for pattern in _ADVICE_PATTERNS:
        if pattern.search(text):
            return RefusalCategory.ADVICE
    for pattern in _DUMP_PATTERNS:
        if pattern.search(text):
            return RefusalCategory.DUMP
    return None