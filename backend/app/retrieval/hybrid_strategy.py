"""Phase 2 — Hybrid retrieval: vector + BM25 (Okapi) hợp nhất bằng RRF.

Bắt được exact-match (số Điều, con số) mà vector search bỏ sót. Thứ tự kết quả
theo RRF, nhưng ``score`` trả về vẫn là cosine similarity → gating/độ tin cậy ở
query_pipeline (ngưỡng 0.3/0.5/0.8) KHÔNG đổi.

Toàn bộ BM25/tokenize/RRF gói trong file này. VectorStore chỉ là storage thuần.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata

from app.retrieval.base import RetrievalStrategy
from app.storage.vector_store import SearchResult, VectorStore

logger = logging.getLogger(__name__)

# RRF constant — làm mượt xếp hạng khi merge 2 danh sách (paper Cormack 2009).
_RRF_K = 60
# BM25 Okapi params.
_BM25_K1 = 1.5
_BM25_B = 0.75
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _remove_diacritics(text: str) -> str:
    """Bỏ dấu tiếng Việt (giữ chữ + số). 'Điều 650' → 'dieu 650'."""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> list[str]:
    """Tokenize: lowercase → bỏ dấu → tách chữ/số. Giữ số (vd '650', '60')."""
    return _TOKEN_RE.findall(_remove_diacritics(text.lower()))


class _BM25:
    """BM25 Okapi trên inverted index. Cho keyword/exact-match mà vector miss."""

    def __init__(self, corpus_tokens: list[list[str]], k1: float = _BM25_K1, b: float = _BM25_B):
        self._k1 = k1
        self._b = b
        self._n = len(corpus_tokens)
        self._doc_len = [len(toks) for toks in corpus_tokens]
        self._avgdl = (sum(self._doc_len) / self._n) if self._n else 0.0

        self._postings: dict[str, list[tuple[int, int]]] = {}
        for idx, toks in enumerate(corpus_tokens):
            tf: dict[str, int] = {}
            for t in toks:
                tf[t] = tf.get(t, 0) + 1
            for t, f in tf.items():
                self._postings.setdefault(t, []).append((idx, f))

        self._idf: dict[str, float] = {}
        for t, postings in self._postings.items():
            df = len(postings)
            self._idf[t] = math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def search(self, query_tokens: list[str], k: int) -> list[tuple[int, float]]:
        """Trả top-k (doc_idx, score) theo BM25, chỉ gồm doc có score > 0."""
        if self._n == 0 or self._avgdl == 0:
            return []
        scores: dict[int, float] = {}
        for t in set(query_tokens):
            postings = self._postings.get(t)
            if not postings:
                continue
            idf = self._idf[t]
            for idx, f in postings:
                denom = f + self._k1 * (1 - self._b + self._b * self._doc_len[idx] / self._avgdl)
                scores[idx] = scores.get(idx, 0.0) + idf * (f * (self._k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:k]


class HybridStrategy(RetrievalStrategy):
    """Vector + BM25 + RRF. Cache BM25 index, rebuild khi corpus đổi (theo data_version)."""

    def __init__(self, store: VectorStore):
        self._store = store
        self._bm25: _BM25 | None = None
        self._built_version: int = -1
        self._ids: list[str] = []
        self._docs: list[str] = []
        self._metas: list[dict] = []
        self._id_to_idx: dict[str, int] = {}

    def _ensure_bm25(self) -> None:
        """Build/rebuild BM25 nếu corpus đã đổi (so data_version của store)."""
        version = self._store.data_version
        if self._bm25 is not None and self._built_version == version:
            return
        self._ids, self._docs, self._metas = self._store.get_corpus()
        self._id_to_idx = {cid: i for i, cid in enumerate(self._ids)}
        self._bm25 = _BM25([_tokenize(doc) for doc in self._docs])
        self._built_version = version
        logger.info("Built BM25 index over %d chunks (version=%d)", len(self._ids), version)

    async def search(
        self, query_vector: list[float], k: int, query_text: str | None = None
    ) -> list[SearchResult]:
        # Không có query_text → suy biến về vector-only.
        if not query_text or not query_text.strip():
            return await self._store.vector_search(query_vector, k)

        count = self._store.count()
        if count == 0:
            return []
        candidate_k = min(max(k * 4, 40), count)

        # --- Nhánh vector ---
        vec_results = await self._store.vector_search(query_vector, candidate_k)
        vec_rank = {r.id: i for i, r in enumerate(vec_results)}
        vec_info = {r.id: r for r in vec_results}

        # --- Nhánh BM25 ---
        self._ensure_bm25()
        bm25_rank: dict[str, int] = {}
        if self._bm25 is not None:
            for rank, (doc_idx, _score) in enumerate(self._bm25.search(_tokenize(query_text), candidate_k)):
                cid = self._ids[doc_idx]
                if cid not in bm25_rank:
                    bm25_rank[cid] = rank

        # --- RRF merge (chỉ để XẾP HẠNG, không thay score) ---
        all_ids = set(vec_rank) | set(bm25_rank)
        if not all_ids:
            return []
        rrf: dict[str, float] = {}
        for cid in all_ids:
            s = 0.0
            if cid in vec_rank:
                s += 1.0 / (_RRF_K + vec_rank[cid] + 1)
            if cid in bm25_rank:
                s += 1.0 / (_RRF_K + bm25_rank[cid] + 1)
            rrf[cid] = s
        top_ids = sorted(all_ids, key=lambda c: rrf[c], reverse=True)[:k]

        # BM25-only hit (ngoài pool vector) → tính cosine để giữ score nhất quán.
        need_cosine = [cid for cid in top_ids if cid not in vec_info]
        cosine_map = self._store.cosine_for_ids(need_cosine, query_vector) if need_cosine else {}

        results: list[SearchResult] = []
        for cid in top_ids:
            if cid in vec_info:
                r = vec_info[cid]
                results.append(SearchResult(id=cid, text=r.text, metadata=r.metadata, score=r.score))
            else:
                idx = self._id_to_idx.get(cid)
                text = self._docs[idx] if idx is not None else ""
                meta = self._metas[idx] if idx is not None else {}
                results.append(SearchResult(id=cid, text=text, metadata=meta, score=cosine_map.get(cid, 0.0)))
        return results  # giữ thứ tự RRF


def build(store: VectorStore) -> HybridStrategy:
    return HybridStrategy(store)
