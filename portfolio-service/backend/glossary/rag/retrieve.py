"""Hybrid vector + BM25 retrieval over the local Chroma index."""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from .store import collection_count, open_collection

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def index_ready(path: Path | None = None) -> bool:
    return collection_count(path=path) > 0


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "")]


@lru_cache(maxsize=4)
def _bm25_bundle(persist_path: str) -> tuple[BM25Okapi, list[str], list[str], list[dict[str, Any]]]:
    collection = open_collection(path=Path(persist_path), create=False)
    total = collection.count()
    if total <= 0:
        empty: list[str] = []
        return BM25Okapi([["placeholder"]]), empty, empty, []
    result = collection.get(include=["documents", "metadatas"])
    ids = list(result.get("ids") or [])
    docs = list(result.get("documents") or [])
    metas = list(result.get("metadatas") or [])
    tokenized = [_tokenize(doc or "") or ["_"] for doc in docs]
    return BM25Okapi(tokenized), ids, docs, metas


def clear_retrieve_cache() -> None:
    _bm25_bundle.cache_clear()


def hybrid_search(
    query: str,
    *,
    k: int = 5,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Return ranked hits with id, score, excerpt, and metadata fields."""
    from ..paths import rag_index_dir

    persist = path or rag_index_dir()
    if not index_ready(path=persist):
        return []

    q = (query or "").strip()
    if not q:
        return []

    collection = open_collection(path=persist, create=False)
    n = max(1, min(int(k), 12))
    vector_hits: dict[str, dict[str, Any]] = {}
    try:
        raw = collection.query(query_texts=[q], n_results=n)
        ids = (raw.get("ids") or [[]])[0]
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        for i, chunk_id in enumerate(ids):
            dist = float(dists[i]) if i < len(dists) else 1.0
            score = 1.0 / (1.0 + max(dist, 0.0))
            meta = metas[i] if i < len(metas) else {}
            vector_hits[str(chunk_id)] = _hit(
                chunk_id=str(chunk_id),
                text=docs[i] if i < len(docs) else "",
                meta=meta or {},
                score=score,
                source="vector",
            )
    except Exception:
        logger.exception("vector search failed")

    bm25_hits: dict[str, dict[str, Any]] = {}
    try:
        bm25, ids, docs, metas = _bm25_bundle(str(persist.resolve()))
        if ids:
            scores = bm25.get_scores(_tokenize(q))
            ranked = sorted(range(len(ids)), key=lambda i: scores[i], reverse=True)[:n]
            max_score = max((scores[i] for i in ranked), default=0.0) or 1.0
            for i in ranked:
                if scores[i] <= 0:
                    continue
                chunk_id = str(ids[i])
                bm25_hits[chunk_id] = _hit(
                    chunk_id=chunk_id,
                    text=docs[i],
                    meta=metas[i] or {},
                    score=float(scores[i]) / float(max_score),
                    source="bm25",
                )
    except Exception:
        logger.exception("bm25 search failed")

    fused: dict[str, dict[str, Any]] = {}
    for bucket in (vector_hits, bm25_hits):
        for chunk_id, hit in bucket.items():
            if chunk_id not in fused:
                fused[chunk_id] = hit
            else:
                fused[chunk_id]["score"] = float(fused[chunk_id]["score"]) + float(hit["score"])
                if hit.get("source") == "vector":
                    fused[chunk_id]["source"] = "hybrid"
                elif fused[chunk_id].get("source") == "vector":
                    fused[chunk_id]["source"] = "hybrid"

    ordered = sorted(fused.values(), key=lambda h: float(h["score"]), reverse=True)
    return ordered[:n]


def read_chunk(chunk_id: str, *, path: Path | None = None, max_chars: int = 2400) -> dict[str, Any] | None:
    from ..paths import rag_index_dir

    persist = path or rag_index_dir()
    if not index_ready(path=persist):
        return None
    collection = open_collection(path=persist, create=False)
    result = collection.get(ids=[chunk_id], include=["documents", "metadatas"])
    ids = result.get("ids") or []
    if not ids:
        return None
    text = (result.get("documents") or [""])[0] or ""
    meta = (result.get("metadatas") or [{}])[0] or {}
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return _hit(chunk_id=chunk_id, text=text, meta=meta, score=1.0, source="read")


def _hit(
    *,
    chunk_id: str,
    text: str,
    meta: dict[str, Any],
    score: float,
    source: str,
) -> dict[str, Any]:
    excerpt = " ".join((text or "").split())
    if len(excerpt) > 320:
        excerpt = excerpt[:319] + "…"
    return {
        "chunk_id": chunk_id,
        "score": float(score),
        "excerpt": excerpt,
        "text": text,
        "module": meta.get("module"),
        "chapter": meta.get("chapter"),
        "url": meta.get("url"),
        "pdf": meta.get("pdf"),
        "kind": meta.get("kind"),
        "term": meta.get("term"),
        "source": source,
    }
