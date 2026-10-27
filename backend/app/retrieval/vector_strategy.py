"""Phase 1 — Vector-only retrieval (cosine similarity thuần qua ChromaDB)."""

from __future__ import annotations

from app.retrieval.base import RetrievalStrategy
from app.storage.vector_store import SearchResult, VectorStore


class VectorStrategy(RetrievalStrategy):
    """Tìm top-k gần nhất theo cosine. Bỏ qua query_text."""

    def __init__(self, store: VectorStore):
        self._store = store

    async def search(
        self, query_vector: list[float], k: int, query_text: str | None = None
    ) -> list[SearchResult]:
        return await self._store.vector_search(query_vector, k)


def build(store: VectorStore) -> VectorStrategy:
    return VectorStrategy(store)
