"""Release 1.11 glossary retrieval (definitions only)."""
from __future__ import annotations

from .agent import run_glossary_agent
from .engine import answer_glossary_message
from .loader import cached_glossary_terms, load_glossary_seed
from .matcher import GlossaryMatcher
from .models import GlossaryResult, GlossaryResultKind, RefusalCategory

__all__ = [
    "GlossaryMatcher",
    "GlossaryResult",
    "GlossaryResultKind",
    "RefusalCategory",
    "answer_glossary_message",
    "cached_glossary_terms",
    "load_glossary_seed",
    "run_glossary_agent",
]