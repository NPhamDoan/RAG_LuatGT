"""RetrievalStrategy — interface cho tầng tìm kiếm (vector hoặc hybrid).

Chọn strategy theo config `RETRIEVAL_STRATEGY`. `load_strategy` nạp động lớp tương ứng;
strategy không có file sẽ báo lỗi rõ ràng.
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
