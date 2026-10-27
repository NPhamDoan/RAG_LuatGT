"""Vector Store — ChromaDB storage thuần + primitives cho tầng retrieval.

Chỉ lo lưu trữ & truy vấn vector cơ bản. Logic hybrid/BM25 nằm ở
app/retrieval/hybrid_strategy.py (Phase 2). Store cung cấp:
- vector_search: top-k theo cosine (Phase 1)
- get_corpus / cosine_for_ids / count: primitives cho hybrid
- data_version: tăng mỗi khi corpus đổi → strategy biết để rebuild cache
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import chromadb

from app.chunking.chunker import Chunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Một kết quả tìm kiếm."""
    id: str
    text: str
    metadata: dict
    score: float


@dataclass
class PaginatedResult:
    """Danh sách văn bản phân trang."""
    items: list[dict]
    total: int
    page: int
    page_size: int


class VectorStore:
    """ChromaDB vector store cho luật giao thông (storage thuần)."""

    def __init__(
        self,
        chroma_client: chromadb.ClientAPI,
        collection_name: str = "luat_giao_thong",
    ):
        self._client = chroma_client
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        # Tăng mỗi khi corpus đổi (add/delete). Retrieval strategy dùng để biết
        # cache (vd BM25 index) có cần rebuild không — thay cho callback.
        self._version = 0

    # Các field seed per-document lưu trong metadata mỗi chunk (prefix "seed").
    # list_documents đọc lại để hiển thị "văn bản này nạp kiểu gì" ở Admin.
    _SEED_FIELDS = (
        "seedVersion", "seedAt", "seedIndexSteps", "seedEnrichEnabled",
        "seedEnrichSource", "seedEnrichModel", "seedRetrieval",
        "seedEmbedding", "seedGitBranch", "seedGitCommit",
    )

    @property
    def data_version(self) -> int:
        return self._version

    def count(self) -> int:
        return self._collection.count()

    def _build_chunk_id(self, so_hieu: str, dieu: str | None, index: int) -> str:
        """ID format: {soHieu}__dieu_{N}."""
        if dieu:
            parts = dieu.split()
            dieu_number = parts[-1] if len(parts) > 1 else str(index)
        else:
            dieu_number = str(index)
        return f"{so_hieu}__dieu_{dieu_number}"

    def _chunk_to_metadata(self, chunk: Chunk) -> dict:
        """Chuyển ChunkMetadata → flat dict cho ChromaDB."""
        meta = chunk.metadata
        return {
            "soHieu": meta.soHieu,
            "tenVanBan": meta.tenVanBan,
            "dieu": meta.dieu or "",
            "khoan": ",".join(meta.khoan) if meta.khoan else "",
            "muc": ",".join(meta.muc) if meta.muc else "",
            "ngayBanHanh": meta.ngayBanHanh.isoformat() if meta.ngayBanHanh else "",
            "ngayHieuLuc": meta.ngayHieuLuc.isoformat() if meta.ngayHieuLuc else "",
            "coQuanBanHanh": meta.coQuanBanHanh,
            "loaiVanBan": meta.loaiVanBan,
        }

    async def add_chunks(
        self,
        chunks: list[Chunk],
        vectors: list[list[float]],
        extra_metadata: dict | None = None,
    ) -> None:
        """Lưu chunks + vectors vào ChromaDB. Dedup bằng upsert.

        extra_metadata: field bổ sung gắn vào MỌI chunk của mẻ này (vd seed info
        per-document: cách nạp, enrich source/model, version). None = không thêm.
        """
        if not chunks:
            return

        extra = extra_metadata or {}
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []
        embeddings: list[list[float]] = []
        id_counts: dict[str, int] = {}

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            base_id = self._build_chunk_id(chunk.metadata.soHieu, chunk.metadata.dieu, i)
            if base_id in id_counts:
                id_counts[base_id] += 1
                chunk_id = f"{base_id}__{id_counts[base_id]}"
            else:
                id_counts[base_id] = 0
                chunk_id = base_id

            ids.append(chunk_id)
            documents.append(chunk.text)
            meta = self._chunk_to_metadata(chunk)
            meta.update(extra)
            metadatas.append(meta)
            embeddings.append(vector)

        self._collection.upsert(
            ids=ids, documents=documents, metadatas=metadatas, embeddings=embeddings
        )
        self._version += 1
        logger.info("Upserted %d chunks (soHieu=%s)", len(ids), chunks[0].metadata.soHieu)

    async def vector_search(self, query_vector: list[float], k: int) -> list[SearchResult]:
        """Phase 1 — top-k gần nhất theo cosine similarity."""
        count = self._collection.count()
        if count == 0:
            return []

        effective_k = min(k, count)
        results = self._collection.query(
            query_embeddings=[query_vector],
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results["ids"] or not results["ids"][0]:
            return []

        search_results: list[SearchResult] = []
        ids = results["ids"][0]
        documents = results["documents"][0] if results["documents"] else [""] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)
        distances = results["distances"][0] if results["distances"] else [1.0] * len(ids)

        for i, chunk_id in enumerate(ids):
            score = 1.0 - distances[i]  # cosine distance → similarity
            search_results.append(
                SearchResult(id=chunk_id, text=documents[i], metadata=metadatas[i], score=score)
            )

        search_results.sort(key=lambda r: r.score, reverse=True)
        return search_results

    def get_corpus(self) -> tuple[list[str], list[str], list[dict]]:
        """Toàn bộ (ids, documents, metadatas) — primitive để hybrid dựng BM25."""
        data = self._collection.get(include=["documents", "metadatas"])
        return (
            data.get("ids", []) or [],
            data.get("documents", []) or [],
            data.get("metadatas", []) or [],
        )

    def cosine_for_ids(self, ids: list[str], query_vector: list[float]) -> dict[str, float]:
        """Cosine similarity của các id chỉ định với query (đọc embedding từ store)."""
        if not ids:
            return {}
        data = self._collection.get(ids=ids, include=["embeddings"])
        got_ids = data.get("ids", []) or []
        embeddings = data.get("embeddings", [])
        out: dict[str, float] = {}
        for i, cid in enumerate(got_ids):
            if i < len(embeddings) and embeddings[i] is not None:
                out[cid] = self._cosine(query_vector, list(embeddings[i]))
        return out

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    async def delete_by_so_hieu(self, so_hieu: str) -> int:
        """Xóa tất cả chunks của một văn bản theo soHieu."""
        results = self._collection.get(where={"soHieu": so_hieu}, include=[])
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            self._version += 1
            logger.info("Deleted %d chunks for soHieu=%s", len(ids), so_hieu)
        return len(ids)

    async def update_document_metadata(self, so_hieu: str, updates: dict) -> int:
        """Cập nhật metadata cho toàn bộ chunk của 1 văn bản — KHÔNG re-embed.

        - Chỉ ghi đè các trường trong `updates` (giữ nguyên các trường khác + text + vector).
        - Nếu đổi soHieu → dựng lại id theo soHieu mới (tái dùng embedding đã lưu).
        Trả về số chunk đã cập nhật.
        """
        data = self._collection.get(
            where={"soHieu": so_hieu},
            include=["embeddings", "documents", "metadatas"],
        )
        old_ids = data.get("ids", []) or []
        if not old_ids:
            return 0

        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        # embeddings là numpy array → không dùng `or []` (ambiguous truth value).
        embeddings = data.get("embeddings")
        if embeddings is None:
            embeddings = []

        new_metas: list[dict] = []
        for m in metadatas:
            nm = dict(m or {})
            nm.update({k: v for k, v in updates.items() if v is not None})
            new_metas.append(nm)

        new_so_hieu = updates.get("soHieu") or so_hieu
        if new_so_hieu != so_hieu:
            # soHieu nằm trong id (`{soHieu}__dieu_...`) → thay tiền tố, giữ phần đuôi.
            new_ids = [new_so_hieu + old_id[len(so_hieu):] for old_id in old_ids]
            emb = [[float(x) for x in e] for e in embeddings]
            self._collection.delete(ids=old_ids)
            self._collection.upsert(
                ids=new_ids, documents=documents, metadatas=new_metas, embeddings=emb
            )
        else:
            self._collection.update(ids=old_ids, metadatas=new_metas)

        self._version += 1
        logger.info(
            "Updated metadata %d chunk (soHieu %s -> %s)", len(old_ids), so_hieu, new_so_hieu
        )
        return len(old_ids)

    async def exists(self, so_hieu: str) -> bool:
        """Kiểm tra văn bản đã tồn tại chưa."""
        results = self._collection.get(where={"soHieu": so_hieu}, include=[], limit=1)
        return bool(results.get("ids"))

    async def list_documents(self, page: int = 1, page_size: int = 20) -> PaginatedResult:
        """Liệt kê văn bản (group by soHieu)."""
        all_data = self._collection.get(include=["metadatas"])
        ids = all_data.get("ids", [])
        metadatas = all_data.get("metadatas", [])

        doc_map: dict[str, dict] = {}
        for i, chunk_id in enumerate(ids):
            meta = metadatas[i] if i < len(metadatas) else {}
            so_hieu = meta.get("soHieu", "")
            if so_hieu not in doc_map:
                entry = {
                    "soHieu": so_hieu,
                    "tenVanBan": meta.get("tenVanBan", ""),
                    "loaiVanBan": meta.get("loaiVanBan", ""),
                    "soChunks": 0,
                }
                # Seed info per-document (nếu có) — đọc từ chunk đầu của nhóm.
                for field in self._SEED_FIELDS:
                    if field in meta:
                        entry[field] = meta[field]
                doc_map[so_hieu] = entry
            doc_map[so_hieu]["soChunks"] += 1

        all_docs = list(doc_map.values())
        total = len(all_docs)
        start = (page - 1) * page_size
        items = all_docs[start: start + page_size]

        return PaginatedResult(items=items, total=total, page=page, page_size=page_size)
