"""Interface cho Embedding provider."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base cho embedding."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Embed 1 đoạn text → vector."""

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed nhiều đoạn → list vectors."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Trả về số chiều embedding."""
