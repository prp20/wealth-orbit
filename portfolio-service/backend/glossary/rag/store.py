"""Chroma persistent store for Varsity POC chunks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from ..paths import rag_index_dir

COLLECTION_NAME = "varsity_poc"


def open_collection(*, path: Path | None = None, create: bool = True) -> Collection:
    persist = path or rag_index_dir()
    persist.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist))
    ef = DefaultEmbeddingFunction()
    if create:
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


def collection_count(path: Path | None = None) -> int:
    try:
        return int(open_collection(path=path, create=False).count())
    except Exception:
        return 0


def upsert_chunks(
    chunks: list[dict[str, Any]],
    *,
    path: Path | None = None,
) -> int:
    """Upsert chunk dicts with keys: id, text, metadata."""
    if not chunks:
        return 0
    collection = open_collection(path=path, create=True)
    ids = [str(c["id"]) for c in chunks]
    documents = [str(c["text"]) for c in chunks]
    metadatas = [dict(c.get("metadata") or {}) for c in chunks]
    # Chroma metadata values must be str|int|float|bool
    clean_meta: list[dict[str, Any]] = []
    for meta in metadatas:
        clean: dict[str, Any] = {}
        for key, value in meta.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                clean[key] = value
            else:
                clean[key] = str(value)
        clean_meta.append(clean)
    collection.upsert(ids=ids, documents=documents, metadatas=clean_meta)
    return len(ids)
