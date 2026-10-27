"""Test PHASE 2: Hybrid retrieval (tokenize + BM25 + RRF) + wiring query_text.

Sau refactor module: BM25/hybrid nằm ở app/retrieval/hybrid_strategy.py.
File này CHỈ có trên các nhánh có Phase 2 (không đưa sang phase-1).
"""

import uuid

import chromadb

from app.chunking.chunker import Chunk, ChunkMetadata
from app.pipelines.query_pipeline import QueryPipeline
from app.retrieval.hybrid_strategy import HybridStrategy, _BM25, _remove_diacritics, _tokenize
from app.storage.vector_store import VectorStore
from tests.fakes import FakeEmbedding, FakeLLM, FakeStore, make_result, make_settings, run


def _store():
    # Tên collection duy nhất mỗi test — EphemeralClient chia sẻ in-memory DB nên
    # tên trùng sẽ rò rỉ dữ liệu chéo giữa các test.
    return VectorStore(chromadb.EphemeralClient(), f"test_hybrid_{uuid.uuid4().hex}")


def _chunk(dieu, text, so_hieu="VB1"):
    return Chunk(text=text, metadata=ChunkMetadata(soHieu=so_hieu, tenVanBan="Luat Test", dieu=dieu))


# ----------------------- tokenize / diacritics -----------------------

def test_remove_diacritics():
    assert _remove_diacritics("Điều thừa kế") == "Dieu thua ke"


def test_tokenize_keeps_numbers_and_strips_diacritics():
    assert _tokenize("Điều 650 thừa kế") == ["dieu", "650", "thua", "ke"]
    assert _tokenize("38/2024/TT-BGTVT") == ["38", "2024", "tt", "bgtvt"]


# ----------------------- BM25 -----------------------

def test_bm25_exact_match_ranks_first():
    corpus = [
        _tokenize("Điều 1 quy định chung về giao thông"),
        _tokenize("Điều 650 quy định về thừa kế tài sản"),
        _tokenize("Điều 8 tốc độ tối đa trong khu dân cư"),
    ]
    hits = _BM25(corpus).search(_tokenize("Điều 650 thừa kế"), k=3)
    assert hits and hits[0][0] == 1


def test_bm25_no_match():
    assert _BM25([_tokenize("giao thông đường bộ")]).search(_tokenize("999 xyz"), k=5) == []


# ----------------------- hybrid search -----------------------
#
# query gần các Điều tốc độ/giao thông; "Điều 650" (thừa kế) trực giao (cosine ~0)
# → vector-only KHÔNG đưa 650 vào top-k. BM25 khớp "650" mới kéo vào hybrid.

_QUERY_VEC = [1.0, 0.0, 0.0, 0.0]


def _seed(store):
    chunks = [
        _chunk("Điều 1", "Điều 1 tốc độ tối đa trong khu dân cư"),
        _chunk("Điều 8", "Điều 8 khoảng cách an toàn giữa các xe"),
        _chunk("Điều 9", "Điều 9 hành vi bị nghiêm cấm khi lái xe"),
        _chunk("Điều 650", "Điều 650 quy định về thừa kế theo pháp luật"),
    ]
    vectors = [
        [0.95, 0.312, 0.0, 0.0],
        [0.90, 0.436, 0.0, 0.0],
        [0.85, 0.527, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],   # Điều 650 trực giao → vector xa
    ]
    run(store.add_chunks(chunks, vectors))


def test_hybrid_rescues_exact_match():
    store = _store()
    _seed(store)
    strat = HybridStrategy(store)

    vec_order = [r.metadata["dieu"] for r in run(store.vector_search(_QUERY_VEC, k=3))]
    hyb_order = [r.metadata["dieu"] for r in run(strat.search(_QUERY_VEC, k=3, query_text="Điều 650 thừa kế"))]

    assert "Điều 650" not in vec_order        # vector-only bỏ sót
    assert "Điều 650" in hyb_order            # BM25 kéo vào


def test_hybrid_score_is_cosine():
    """Score trả về vẫn là cosine similarity → gating Phase 1 không đổi."""
    store = _store()
    _seed(store)
    strat = HybridStrategy(store)
    for r in run(strat.search(_QUERY_VEC, k=4, query_text="Điều 650 thừa kế")):
        assert -1.0001 <= r.score <= 1.0001


def test_hybrid_no_query_text_falls_back_to_vector():
    """Không có query_text → hybrid suy biến về vector-only."""
    store = _store()
    _seed(store)
    strat = HybridStrategy(store)
    res = run(strat.search(_QUERY_VEC, k=3))
    assert [r.metadata["dieu"] for r in res] == ["Điều 1", "Điều 8", "Điều 9"]


# ----------------------- BM25 cache theo data_version -----------------------

def test_bm25_cache_tracks_data_version():
    """BM25 rebuild khi corpus đổi (store.data_version tăng)."""
    store = _store()
    _seed(store)
    strat = HybridStrategy(store)

    strat._ensure_bm25()
    assert strat._built_version == store.data_version

    run(store.add_chunks([_chunk("Điều 2", "Điều 2 nội dung mới", so_hieu="VB2")], [[0.5, 0.5, 0.0, 0.0]]))
    assert strat._built_version != store.data_version   # store đã bump, cache cũ

    strat._ensure_bm25()
    assert strat._built_version == store.data_version   # đã rebuild khớp lại


def test_bm25_rebuilds_reflect_new_docs():
    """Sau khi thêm doc, BM25 index bao gồm doc mới."""
    store = _store()
    _seed(store)
    strat = HybridStrategy(store)
    run(strat.search(_QUERY_VEC, k=3, query_text="Điều 650"))   # build lần đầu
    n_before = len(strat._ids)
    run(store.add_chunks([_chunk("Điều 2", "Điều 2 nội dung mới", so_hieu="VB2")], [[0.5, 0.5, 0.0, 0.0]]))
    run(strat.search(_QUERY_VEC, k=3, query_text="Điều 650"))   # rebuild
    assert len(strat._ids) == n_before + 1


# ----------------------- wiring: pipeline truyền query_text -----------------------

def test_query_text_passed_to_retrieval():
    """Pipeline truyền query_text vào retrieval.search để kích hoạt hybrid."""
    fake_retrieval = FakeStore([make_result("Điều 8", 0.9)])
    pipe = QueryPipeline(FakeLLM(), FakeEmbedding(), fake_retrieval, make_settings())
    run(pipe.process_query("Điều 650 thừa kế"))
    assert fake_retrieval.last_query_text == "Điều 650 thừa kế"
    assert fake_retrieval.last_k == 8
