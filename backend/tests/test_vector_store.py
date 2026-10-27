"""Test VectorStore — PHASE 1: vector-only (cosine) search.

Chỉ dùng API có từ Phase 1 (add_chunks/search/exists/list/delete). KHÔNG chạm
BM25/hybrid (Phase 2) → file này chạy được trên cả nhánh phase-1 lẫn phase-2.
"""

import uuid

import chromadb

from app.storage.vector_store import VectorStore
from tests.fakes import fake_vec, make_chunk, run


def _store():
    # Tên collection duy nhất mỗi test (EphemeralClient chia sẻ in-memory DB).
    return VectorStore(chromadb.EphemeralClient(), f"test_vs_{uuid.uuid4().hex}")


def test_add_search_delete_vector_only():
    store = _store()
    chunks = [
        make_chunk("VB1", "Điều 8", "Tốc độ tối đa trong khu dân cư"),
        make_chunk("VB1", "Điều 9", "Khoảng cách an toàn giữa hai xe"),
    ]
    vectors = [fake_vec(1.0), fake_vec(2.0)]
    run(store.add_chunks(chunks, vectors))

    # vector-only (cosine)
    results = run(store.vector_search(fake_vec(1.0), k=2))
    assert len(results) == 2
    assert results[0].metadata["dieu"] == "Điều 8"   # vector trùng query → đứng đầu
    assert results[0].score > 0.99

    assert run(store.exists("VB1")) is True
    assert run(store.list_documents()).total == 1     # group theo soHieu

    deleted = run(store.delete_by_so_hieu("VB1"))
    assert deleted == 2
    assert run(store.exists("VB1")) is False


def test_search_empty_store_returns_empty():
    assert run(_store().vector_search(fake_vec(1.0), k=5)) == []
