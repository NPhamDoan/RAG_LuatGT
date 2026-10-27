"""HuggingFace Embedding — sentence-transformers + multilingual-e5-large."""

import asyncio
import logging
import threading

from sentence_transformers import SentenceTransformer

from app.providers.embedding_provider import EmbeddingProvider

logger = logging.getLogger(__name__)


# Số chunk mỗi lô để báo tiến độ khi embed (nhỏ hơn = log mịn hơn nhưng chậm hơn chút).
_PROGRESS_BATCH_SIZE = 16


class HuggingFaceEmbedding(EmbeddingProvider):
    """Embedding dùng sentence-transformers.

    Model e5 yêu cầu prefix "query: " (câu hỏi) / "passage: " (document).
    """

    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        self._model_name = model_name
        self._model: SentenceTransformer | None = None
        self._load_lock = threading.Lock()

    @property
    def model(self) -> SentenceTransformer:
        """Lazy-load model lần đầu (thread-safe, tránh nạp trùng ~2GB)."""
        if self._model is None:
            with self._load_lock:
                # Double-check sau khi giành lock: luồng khác có thể đã nạp xong
                if self._model is None:
                    logger.info(
                        "Nạp embedding model '%s' (lần đầu, ~2GB — có thể mất vài phút)...",
                        self._model_name,
                    )
                    self._model = SentenceTransformer(self._model_name)
                    logger.info("Nạp embedding model xong.")
        return self._model

    def get_dimension(self) -> int:
        return 1024

    async def embed_text(self, text: str, prefix: str = "query: ") -> list[float]:
        """Embed 1 text (mặc định prefix query)."""
        prefixed = f"{prefix}{text}"
        embedding = await asyncio.to_thread(
            self.model.encode, prefixed, normalize_embeddings=True
        )
        return embedding.tolist()

    async def embed_batch(self, texts: list[str], prefix: str = "passage: ") -> list[list[float]]:
        """Embed batch (mặc định prefix passage cho indexing).

        Chia thành lô nhỏ để log tiến độ. Model.encode đã tự song song ở tầng native
        nên KHÔNG dùng thêm thread Python (sẽ tranh nhân CPU, chậm hơn).
        """
        if not texts:
            return []
        prefixed = [f"{prefix}{t}" for t in texts]
        total = len(prefixed)
        vectors: list[list[float]] = []
        for start in range(0, total, _PROGRESS_BATCH_SIZE):
            sub = prefixed[start : start + _PROGRESS_BATCH_SIZE]
            embeddings = await asyncio.to_thread(
                self.model.encode, sub, normalize_embeddings=True
            )
            vectors.extend(embeddings.tolist())
            done = min(start + _PROGRESS_BATCH_SIZE, total)
            logger.info("Embed tiến độ: %d/%d chunk.", done, total)
        return vectors
