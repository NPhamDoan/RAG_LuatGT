"""RetrievalStrategy — interface cho tầng tìm kiếm (Phase 1 vector, Phase 2 hybrid...).

Chọn strategy theo config `RETRIEVAL_STRATEGY`. Strategy nào không được ship (file
không có) thì `load_strategy` sẽ báo lỗi rõ ràng — đúng tinh thần "code vắng = không chạy".
"""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod

from app.storage.vector_store import SearchResult, VectorStore


class RetrievalStrategy(ABC):
    """Hợp đồng chung: nhận query vector (+ text) → trả list SearchResult đã xếp hạng."""

    @abstractmethod
    async def search(
        self, query_vector: list[float], k: int, query_text: str | None = None
    ) -> list[SearchResult]:
        ...


def load_strategy(name: str, store: VectorStore) -> RetrievalStrategy:
    """Nạp động strategy theo tên: 'vector' → vector_strategy.py, 'hybrid' → hybrid_strategy.py."""
    module = importlib.import_module(f"app.retrieval.{name}_strategy")
    return module.build(store)
