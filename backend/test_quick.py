"""Quick smoke test — verify chunker + vector store + pipeline wiring."""

import asyncio
import sys
from datetime import date

sys.path.insert(0, ".")

import chromadb

from app.chunking.chunker import Chunk, ChunkMetadata, DocumentMetadata, VietnameseLawChunker
from app.storage.vector_store import VectorStore


async def test_vector_store():
    print("=== Test Vector Store ===")
    client = chromadb.EphemeralClient()
    store = VectorStore(client, "test_collection")

    chunks = [
        Chunk(
            text="Điều 8. Tốc độ tối đa: xe máy 40 km/h, ô tô 60 km/h trong khu vực đông dân cư.",
            metadata=ChunkMetadata(
                soHieu="31/2019/TT-BGTVT", tenVanBan="Thông tư tốc độ",
                dieu="Điều 8", ngayBanHanh=date(2019, 7, 12), ngayHieuLuc=date(2020, 1, 15),
            ),
        ),
        Chunk(
            text="Điều 12. Người lái xe phải tuân thủ tốc độ do cơ quan có thẩm quyền quy định.",
            metadata=ChunkMetadata(
                soHieu="36/2024/QH15", tenVanBan="Luật TTATGT 2024",
                dieu="Điều 12", ngayBanHanh=date(2024, 6, 27), ngayHieuLuc=date(2025, 1, 1),
            ),
        ),
    ]
    # Fake vectors (thực tế dùng embedding model)
    vectors = [[0.1 + i * 0.01] * 1024 for i in range(len(chunks))]

    await store.add_chunks(chunks, vectors)
    print(f"  Added {len(chunks)} chunks")

    results = await store.search([0.1] * 1024, k=2)
    print(f"  Search: {len(results)} results")
    for r in results:
        print(f"    score={r.score:.3f} | {r.metadata.get('dieu')} | {r.text[:50]}...")

    assert await store.exists("31/2019/TT-BGTVT")
    print("  Exists check: OK")

    paged = await store.list_documents()
    print(f"  List: {paged.total} documents")

    deleted = await store.delete_by_so_hieu("31/2019/TT-BGTVT")
    print(f"  Deleted: {deleted} chunks")
    assert not await store.exists("31/2019/TT-BGTVT")
    print("  Delete check: OK")
    print("  PASS\n")


def test_chunker():
    print("=== Test Chunker ===")
    chunker = VietnameseLawChunker()
    text = """Điều 8. Tốc độ tối đa cho phép
1. Trong khu vực đông dân cư:
a) Xe máy: 40 km/h
b) Ô tô: 60 km/h
2. Ngoài khu vực đông dân cư:
a) Xe máy: 60 km/h
b) Ô tô: 80 km/h

Điều 9. Khoảng cách an toàn
1. Khi trời khô ráo, tốc độ 60 km/h: khoảng cách tối thiểu 35m.
2. Khi trời mưa: khoảng cách gấp đôi."""

    meta = DocumentMetadata(
        soHieu="31/2019/TT-BGTVT", tenVanBan="Thông tư tốc độ",
        ngayBanHanh=date(2019, 7, 12), ngayHieuLuc=date(2020, 1, 15),
        coQuanBanHanh="Bộ GTVT", loaiVanBan="Thông tư",
    )
    chunks = chunker.chunk_document(text, meta)
    print(f"  {len(chunks)} chunks từ 2 Điều")
    for c in chunks:
        print(f"    {c.metadata.dieu}: khoan={c.metadata.khoan} | {c.text[:60]}...")

    assert len(chunks) == 2
    assert chunks[0].metadata.dieu == "Điều 8"
    assert chunks[1].metadata.dieu == "Điều 9"
    assert "1" in chunks[0].metadata.khoan
    print("  PASS\n")


def test_chunker_fallback():
    print("=== Test Chunker Fallback (no Điều) ===")
    chunker = VietnameseLawChunker(chunk_size=50, chunk_overlap=10, max_chunk_size=80)
    text = "Phụ lục I: Bảng mức phạt vi phạm hành chính. " * 10
    meta = DocumentMetadata(
        soHieu="100/2019", tenVanBan="Nghị định phạt",
        ngayBanHanh=date(2019, 1, 1), ngayHieuLuc=date(2019, 3, 1),
    )
    chunks = chunker.chunk_document(text, meta)
    print(f"  {len(chunks)} chunks (fallback by size)")
    assert len(chunks) > 1
    assert all(c.metadata.dieu is None for c in chunks)
    print("  PASS\n")


if __name__ == "__main__":
    test_chunker()
    test_chunker_fallback()
    asyncio.run(test_vector_store())
    print("=" * 40)
    print("ALL TESTS PASSED!")
