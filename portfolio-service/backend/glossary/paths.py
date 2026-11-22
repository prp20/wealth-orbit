"""Resolve repo-rooted glossary seed paths."""
from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # portfolio-service/backend/glossary/paths.py → repo root
    return Path(__file__).resolve().parents[3]


def varsity_docs_dir() -> Path:
    return repo_root() / "docs" / "varsity_docs"


def glossary_seed_path() -> Path:
    return varsity_docs_dir() / "glossary_seed.json"


def chapter_index_path() -> Path:
    return varsity_docs_dir() / "chapter_index.json"


def extracted_markdown_dir() -> Path:
    return varsity_docs_dir() / "extracted"


def rag_index_dir() -> Path:
    return varsity_docs_dir() / ".rag_index"