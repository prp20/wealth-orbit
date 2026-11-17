"""Term and alias matching against the glossary seed."""
from __future__ import annotations

import re

from .loader import cached_glossary_terms
from .models import GlossaryResult, GlossaryResultKind, GlossaryTerm

_QUESTION_EXTRACT = re.compile(
    r"^(?:"
    r"what(?:'s| is| are)\s+(?:an?\s+)?"
    r"|define\s+"
    r"|meaning of\s+(?:an?\s+)?"
    r"|explain\s+(?:an?\s+)?"
    r"|tell me about\s+(?:an?\s+)?"
    r")(?P<term>.+?)\s*\??\s*$",
    re.IGNORECASE,
)


def normalize_phrase(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = cleaned.rstrip("?.!")
    return " ".join(cleaned.split())


def _build_lookup(terms: tuple[GlossaryTerm, ...]) -> dict[str, GlossaryTerm]:
    lookup: dict[str, GlossaryTerm] = {}
    for entry in terms:
        lookup[normalize_phrase(entry.term)] = entry
        for alias in entry.aliases:
            lookup[normalize_phrase(alias)] = entry
    return lookup


def _extract_query_term(message: str) -> str | None:
    match = _QUESTION_EXTRACT.match(message.strip())
    if match:
        return match.group("term").strip()
    return None


def _phrase_in_text(phrase: str, text: str) -> bool:
    """True when phrase appears as a whole token sequence, not a bare substring."""
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text, re.IGNORECASE) is not None


class GlossaryMatcher:
    def __init__(self, terms: tuple[GlossaryTerm, ...] | None = None) -> None:
        self._terms = terms if terms is not None else cached_glossary_terms()
        self._lookup = _build_lookup(self._terms)
        self._by_length = sorted(self._lookup.keys(), key=len, reverse=True)

    def match(self, message: str) -> GlossaryTerm | None:
        text = message.strip()
        if not text:
            return None

        candidate = _extract_query_term(text)
        if candidate is not None:
            hit = self._lookup.get(normalize_phrase(candidate))
            if hit is not None:
                return hit

        direct = self._lookup.get(normalize_phrase(text))
        if direct is not None:
            return direct

        normalized = normalize_phrase(text)
        search_in = normalize_phrase(candidate) if candidate is not None else normalized
        for key in self._by_length:
            if _phrase_in_text(key, search_in):
                return self._lookup[key]
        return None

    def to_result(self, message: str) -> GlossaryResult:
        entry = self.match(message)
        if entry is None:
            return GlossaryResult(kind=GlossaryResultKind.UNKNOWN)
        return GlossaryResult(
            kind=GlossaryResultKind.MATCH,
            term=entry.term,
            definition=entry.definition,
            sources=entry.sources,
        )