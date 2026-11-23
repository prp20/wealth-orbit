"""Public glossary payload sanitization."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "portfolio-service"))

from backend.glossary.public_payload import sanitize_public_agent_payload


def test_sanitize_strips_traces_and_caps_excerpts() -> None:
    long_excerpt = "word " * 200
    payload = {
        "assistant_message": "An IPO is a first public share sale.",
        "mode": "multi_agent",
        "agent_trace": [{"agent": "retriever", "tools": [{"result": {"text": "SECRET CHUNK"}}]}],
        "tool_trace": [{"name": "read_chunk", "result": {"text": "SECRET"}}],
        "citations": [
            {
                "module": 1,
                "chapter": "IPO",
                "url": "https://zerodha.com/varsity/chapter/ipo/",
                "term": "IPO",
                "excerpt": long_excerpt,
                "chunk_id": "m1-c0",
            }
        ],
    }
    out = sanitize_public_agent_payload(payload)
    assert "agent_trace" not in out
    assert "tool_trace" not in out
    assert "chunk_id" not in out["citations"][0]
    assert len(out["citations"][0]["excerpt"]) < len(long_excerpt)
    assert "SECRET" not in str(out)
