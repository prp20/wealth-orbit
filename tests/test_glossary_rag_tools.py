"""Fixture-based corpus tools (no real PDFs in CI)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary.rag.retrieve import clear_retrieve_cache, hybrid_search, index_ready, read_chunk
from backend.glossary.rag.store import upsert_chunks
from backend.glossary import tools as glossary_tools


@pytest.fixture()
def fixture_index(tmp_path: Path):
    chunks = [
        {
            "id": "m1-c0",
            "text": (
                "An Initial Public Offering (IPO) is when a private company offers its "
                "shares to the public for the first time."
            ),
            "metadata": {
                "module": 1,
                "chapter": "The IPO Markets",
                "url": "https://zerodha.com/varsity/chapter/ipo/",
                "kind": "pdf",
            },
        },
        {
            "id": "seed-roe",
            "text": "ROE Return on Equity measures how efficiently a company uses shareholder equity.",
            "metadata": {
                "module": 3,
                "chapter": "Financial Ratios",
                "url": "https://zerodha.com/varsity/chapter/ratio-analysis/",
                "kind": "seed",
                "term": "ROE",
            },
        },
    ]
    upsert_chunks(chunks, path=tmp_path)
    clear_retrieve_cache()
    yield tmp_path
    clear_retrieve_cache()


def test_index_ready_and_hybrid_search(fixture_index: Path) -> None:
    assert index_ready(path=fixture_index)
    hits = hybrid_search("IPO public offering", k=3, path=fixture_index)
    assert hits
    assert any("IPO" in (h.get("excerpt") or "") for h in hits)


def test_read_chunk(fixture_index: Path) -> None:
    hit = read_chunk("m1-c0", path=fixture_index)
    assert hit is not None
    assert hit["chunk_id"] == "m1-c0"
    assert "IPO" in (hit.get("text") or "")


def test_search_corpus_tool(monkeypatch: pytest.MonkeyPatch, fixture_index: Path) -> None:
    monkeypatch.setattr(
        "backend.glossary.rag.retrieve.index_ready",
        lambda path=None: True,
    )
    monkeypatch.setattr(
        "backend.glossary.rag.retrieve.hybrid_search",
        lambda query, k=5, path=None: hybrid_search(query, k=k, path=fixture_index),
    )
    result = glossary_tools.search_corpus("IPO", k=2)
    assert result["hits"]
    assert result["hits"][0]["chunk_id"] == "m1-c0"


def test_execute_allowlists_corpus_tools() -> None:
    assert "search_corpus" in glossary_tools.ALLOWED_TOOL_NAMES
    assert "read_chunk" in glossary_tools.ALLOWED_TOOL_NAMES
    assert "lookup_chapter" in glossary_tools.ALLOWED_TOOL_NAMES


def test_search_corpus_reports_not_built(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.glossary.rag.retrieve.index_ready",
        lambda path=None: False,
    )
    result = glossary_tools.search_corpus("IPO", k=2)
    assert result["error"] == "corpus_not_built"
    assert result["hits"] == []


def test_lookup_chapter_tool() -> None:
    result = glossary_tools.lookup_chapter(module=1, chapter_title="IPO")
    assert isinstance(result, dict)
    assert "found" in result
    if result["found"]:
        assert result.get("chapter")
        assert result.get("url")
