"""Resolve repo-rooted screen plugin paths."""
from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    # portfolio-service/backend/screen_plugins/paths.py → repo root
    return Path(__file__).resolve().parents[3]


def registry_path() -> Path:
    return repo_root() / "screens" / "registry.yaml"


def resolve_plugin_root(relative: str) -> Path:
    root = repo_root() / relative
    return root.resolve()
