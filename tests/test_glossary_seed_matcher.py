"""Release 1.11: glossary seed loader, matcher, and intent guards."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary import (
    GlossaryResultKind,
    RefusalCategory,
    answer_glossary_message,
    load_glossary_seed,
)
from backend.glossary.paths import glossary_seed_path


def test_seed_file_resolves_from_repo_root():
    assert glossary_seed_path().is_file()


def test_load_glossary_seed_has_ipo():
    terms = load_glossary_seed()
    names = {t.term for t in terms}
    assert "IPO" in names
    assert len(terms) >= 5


def test_what_is_ipo_returns_definition_and_sources():
    result = answer_glossary_message("What is IPO?")
    assert result.kind is GlossaryResultKind.MATCH
    assert result.term == "IPO"
    assert result.definition
    assert "public" in result.definition.lower()
    assert len(result.sources) >= 1
    assert all(s.url.startswith("https://") for s in result.sources)


def test_ipo_alias_initial_public_offering():
    result = answer_glossary_message("meaning of initial public offering")
    assert result.kind is GlossaryResultKind.MATCH
    assert result.term == "IPO"


def test_refuses_buy_sell_advice():
    result = answer_glossary_message("Should I buy HDFC Bank stock now?")
    assert result.kind is GlossaryResultKind.REFUSAL
    assert result.refusal_category is RefusalCategory.ADVICE
    assert "buy" in result.refusal_reason.lower() or "advice" in result.refusal_reason.lower()


def test_refuses_varsity_dump_request():
    result = answer_glossary_message("Paste the full Varsity chapter on candlesticks here")
    assert result.kind is GlossaryResultKind.REFUSAL
    assert result.refusal_category is RefusalCategory.DUMP
    assert "chapter" in result.refusal_reason.lower() or "pdf" in result.refusal_reason.lower()


def test_unknown_term():
    result = answer_glossary_message("What is zzyxnonexistent term?")
    assert result.kind is GlossaryResultKind.UNKNOWN