"""Load curated glossary seed JSON."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .models import GlossaryTerm
from .paths import glossary_seed_path


def _parse_seed(data: dict[str, Any]) -> tuple[GlossaryTerm, ...]:
    terms_raw = data.get("terms")
    if not isinstance(terms_raw, list):
        raise ValueError("glossary_seed.json: 'terms' must be a list")
    return tuple(GlossaryTerm.from_dict(item) for item in terms_raw)


def load_glossary_seed(path: str | None = None) -> tuple[GlossaryTerm, ...]:
    seed_path = glossary_seed_path() if path is None else path
    with open(seed_path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("glossary_seed.json must be a JSON object")
    return _parse_seed(data)


@lru_cache(maxsize=1)
def cached_glossary_terms() -> tuple[GlossaryTerm, ...]:
    return load_glossary_seed()