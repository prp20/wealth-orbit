"""Local Varsity corpus RAG (POC — extracted text stays gitignored)."""
from __future__ import annotations

from .retrieve import hybrid_search, index_ready, read_chunk
from .store import COLLECTION_NAME, open_collection

__all__ = [
    "COLLECTION_NAME",
    "hybrid_search",
    "index_ready",
    "open_collection",
    "read_chunk",
]
