#!/usr/bin/env python3
"""Build local Varsity markdown + Chroma index for glossary RAG POC.

Usage (from repo root):
  uv run python portfolio-service/scripts/glossary/ingest_varsity_corpus.py

Requires PDFs under docs/varsity_docs/ (gitignored). Extracted text and the
vector index are also gitignored — do not commit or redistribute.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# portfolio-service is also on path for `backend.*`
PS = ROOT / "portfolio-service"
if str(PS) not in sys.path:
    sys.path.insert(0, str(PS))

from backend.glossary.rag.ingest import ingest_varsity_corpus  # noqa: E402
from backend.glossary.rag.retrieve import hybrid_search  # noqa: E402


def main() -> int:
    report = ingest_varsity_corpus(progress=print)
    print(
        f"done: modules_ok={report.modules_ok} missing={report.modules_missing} "
        f"md={report.markdown_files} chunks={report.chunks}"
    )
    hits = hybrid_search("IPO", k=3)
    print("smoke search IPO:")
    for hit in hits:
        print(
            f"  score={hit['score']:.3f} module={hit.get('module')} "
            f"chapter={hit.get('chapter')!r} excerpt={hit.get('excerpt')!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
