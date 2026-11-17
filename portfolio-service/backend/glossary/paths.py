"""Resolve repo-rooted glossary seed paths."""
from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # portfolio-service/backend/glossary/paths.py → repo root
    return Path(__file__).resolve().parents[3]


def glossary_seed_path() -> Path:
    return repo_root() / "docs" / "varsity_docs" / "glossary_seed.json"