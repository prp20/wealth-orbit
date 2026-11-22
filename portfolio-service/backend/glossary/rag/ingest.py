"""PDF → markdown → Chroma ingest for Varsity POC corpus."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import tiktoken

from ..loader import load_glossary_seed
from ..paths import (
    chapter_index_path,
    extracted_markdown_dir,
    glossary_seed_path,
    varsity_docs_dir,
)
from .retrieve import clear_retrieve_cache
from .store import upsert_chunks

logger = logging.getLogger(__name__)

_SLUG = re.compile(r"[^a-z0-9]+")
_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class IngestReport:
    modules_ok: list[int]
    modules_missing: list[int]
    chunks: int
    markdown_files: int


def _slug(text: str) -> str:
    s = _SLUG.sub("-", (text or "").lower()).strip("-")
    return s or "chapter"


def _extract_pdf_text(pdf_path: Path) -> str:
    try:
        import fitz  # PyMuPDF

        parts: list[str] = []
        with fitz.open(pdf_path) as doc:
            for page in doc:
                parts.append(page.get_text("text") or "")
        text = "\n\n".join(parts).strip()
        if text:
            return text
    except Exception:
        logger.exception("PyMuPDF failed for %s; trying pypdf", pdf_path)

    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(parts).strip()


def _chunk_text(text: str, *, target_tokens: int = 650, overlap: int = 100) -> list[str]:
    tokens = _ENC.encode(text or "")
    if not tokens:
        return []
    if len(tokens) <= target_tokens:
        return [_ENC.decode(tokens)]
    chunks: list[str] = []
    start = 0
    step = max(1, target_tokens - overlap)
    while start < len(tokens):
        end = min(len(tokens), start + target_tokens)
        chunks.append(_ENC.decode(tokens[start:end]))
        if end >= len(tokens):
            break
        start += step
    return chunks


def _write_markdown(
    *,
    out_path: Path,
    module: int,
    title: str,
    source_pdf: str,
    varsity_url: str,
    body: str,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    front = (
        f"---\nmodule: {module}\ntitle: {json.dumps(title)}\n"
        f"source_pdf: {json.dumps(source_pdf)}\nvarsity_url: {json.dumps(varsity_url)}\n---\n\n"
    )
    out_path.write_text(front + body.strip() + "\n", encoding="utf-8")


def _best_chapter(meta_module: dict[str, Any], chunk_text: str) -> dict[str, Any] | None:
    chapters = meta_module.get("chapters") or []
    if not chapters:
        return None
    lower = chunk_text.lower()
    for chapter in chapters:
        title = str(chapter.get("title") or "")
        if title and title.lower() in lower[:800]:
            return chapter
    # Fallback: first chapter URL for the module
    return chapters[0] if isinstance(chapters[0], dict) else None


def ingest_varsity_corpus(
    *,
    docs_dir: Path | None = None,
    extracted_dir: Path | None = None,
    index_path: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> IngestReport:
    base = docs_dir or varsity_docs_dir()
    out_root = extracted_dir or extracted_markdown_dir()
    index_file = base / "chapter_index.json"
    if not index_file.exists():
        index_file = chapter_index_path()

    data = json.loads(index_file.read_text(encoding="utf-8"))
    modules = data.get("modules") or []
    report = IngestReport(modules_ok=[], modules_missing=[], chunks=0, markdown_files=0)
    all_chunks: list[dict[str, Any]] = []

    def log(msg: str) -> None:
        if progress:
            progress(msg)
        else:
            logger.info(msg)

    for mod in modules:
        module_num = int(mod.get("module") or 0)
        pdf_local = mod.get("pdf_local")
        if not pdf_local:
            report.modules_missing.append(module_num)
            log(f"module {module_num}: no pdf_local — skip")
            continue
        pdf_path = base / str(pdf_local)
        if not pdf_path.exists():
            report.modules_missing.append(module_num)
            log(f"module {module_num}: missing PDF {pdf_local}")
            continue

        log(f"module {module_num}: extracting {pdf_local}")
        text = _extract_pdf_text(pdf_path)
        if not text.strip():
            report.modules_missing.append(module_num)
            log(f"module {module_num}: empty extract")
            continue

        title = str(mod.get("title") or f"Module {module_num}")
        md_path = out_root / f"module_{module_num:02d}" / f"{_slug(title)}.md"
        _write_markdown(
            out_path=md_path,
            module=module_num,
            title=title,
            source_pdf=str(pdf_local),
            varsity_url=str(mod.get("url") or ""),
            body=text,
        )
        report.markdown_files += 1
        report.modules_ok.append(module_num)

        for idx, piece in enumerate(_chunk_text(text)):
            chapter = _best_chapter(mod, piece) or {}
            chunk_id = f"m{module_num}-c{idx}"
            all_chunks.append(
                {
                    "id": chunk_id,
                    "text": piece,
                    "metadata": {
                        "module": module_num,
                        "chapter": str(chapter.get("title") or title),
                        "url": str(chapter.get("url") or mod.get("url") or ""),
                        "pdf": str(pdf_local),
                        "kind": "pdf",
                    },
                }
            )

    # Seed terms as high-priority docs
    if glossary_seed_path().exists():
        for term in load_glossary_seed():
            body = f"{term.term}\nAliases: {', '.join(term.aliases)}\n\n{term.definition}"
            sources = term.sources or []
            chapter = sources[0].chapter if sources else ""
            url = sources[0].url if sources else ""
            module = sources[0].module if sources else 0
            all_chunks.append(
                {
                    "id": f"seed-{_slug(term.term)}",
                    "text": body,
                    "metadata": {
                        "module": int(module or 0),
                        "chapter": chapter,
                        "url": url,
                        "pdf": "",
                        "kind": "seed",
                        "term": term.term,
                    },
                }
            )

    from ..paths import rag_index_dir

    persist = index_path or rag_index_dir()
    report.chunks = upsert_chunks(all_chunks, path=persist)
    clear_retrieve_cache()
    log(f"indexed {report.chunks} chunks → {persist}")
    return report
