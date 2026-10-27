"""Fake providers/store + helpers dùng chung cho test.

Chỉ phụ thuộc code Phase 1 → an toàn để đặt trên cả nhánh phase-1 lẫn phase-2.
"""

import asyncio
import math

from app.chunking.chunker import Chunk, ChunkMetadata
from app.config import Settings
from app.providers.embedding_provider import EmbeddingProvider
from app.providers.llm_provider import LLMProvider, LLMResponse
from app.storage.vector_store import SearchResult


def run(coro):
    """Chạy coroutine trong test đồng bộ."""
    return asyncio.run(coro)


def fake_vec(seed: float, dim: int = 16) -> list[float]:
    """Vector giả định tất định, đã chuẩn hóa (để so cosine)."""
    v = [math.sin(seed * (i + 1)) for i in range(dim)]
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v]


def make_chunk(so_hieu: str, dieu: str, text: str) -> Chunk:
    return Chunk(text=text, metadata=ChunkMetadata(soHieu=so_hieu, tenVanBan="Luat Test", dieu=dieu))


class FakeEmbedding(EmbeddingProvider):
    def __init__(self):
        self.last_batch: list[str] | None = None  # ghi lại text truyền vào embed_batch

    async def embed_text(self, text: str) -> list[float]:
        return [0.1] * 8

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.last_batch = list(texts)
        return [[0.1] * 8 for _ in texts]

    def get_dimension(self) -> int:
        return 8


class FakeIndexStore:
    """Store giả cho document pipeline: ghi lại chunks/vectors đã add."""

    def __init__(self, exists: bool = False):
        self._exists = exists
        self.added_chunks = None
        self.added_vectors = None
        self.added_extra = None
        self.deleted = None

    async def exists(self, so_hieu: str) -> bool:
        return self._exists

    async def delete_by_so_hieu(self, so_hieu: str) -> int:
        self.deleted = so_hieu
        return 1

    async def add_chunks(self, chunks, vectors, extra_metadata=None) -> None:
        self.added_chunks = list(chunks)
        self.added_vectors = list(vectors)
        self.added_extra = extra_metadata

    def count(self) -> int:
        return len(self.added_chunks or [])


class FakeLLM(LLMProvider):
    def __init__(self, content: str = "**1. Phân tích**\nNội dung [1].", raise_exc: bool = False):
        self._content = content
        self._raise = raise_exc
        self.called = False

    async def generate(self, prompt: str, system_prompt: str = "") -> LLMResponse:
        self.called = True
        if self._raise:
            raise RuntimeError("LLM down")
        return LLMResponse(content=self._content)


class FakeStore:
    """Store giả: trả results định sẵn, ghi lại tham số search (để kiểm tra wiring)."""

    def __init__(self, results):
        self._results = results
        self.last_query_text = None
        self.last_k = None

    async def search(self, query_vector, k=5, query_text=None):
        self.last_query_text = query_text
        self.last_k = k
        return self._results


def make_result(dieu: str, score: float, so_hieu: str = "36/2024/QH15") -> SearchResult:
    return SearchResult(
        id=f"{so_hieu}__{dieu}",
        text=f"Nội dung {dieu} về giao thông.",
        metadata={
            "soHieu": so_hieu,
            "tenVanBan": "Luật TTATGT 2024",
            "dieu": dieu,
            "khoan": "1",
            "ngayHieuLuc": "2025-01-01",
        },
        score=score,
    )


def make_settings() -> Settings:
    return Settings(
        similarity_threshold_min=0.3,
        similarity_threshold_confident=0.5,
        confidence_high_threshold=0.8,
        retrieval_top_k=8,
        synthesis_max_chunks=6,
        synthesis_max_chars_per_chunk=2000,
    )
