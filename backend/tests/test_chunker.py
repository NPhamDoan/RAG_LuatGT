"""Test VietnameseLawChunker — cắt theo Điều + fallback theo kích thước."""

from datetime import date

from app.chunking.chunker import DocumentMetadata, VietnameseLawChunker


def _meta(so_hieu="31/2019/TT-BGTVT"):
    return DocumentMetadata(
        soHieu=so_hieu,
        tenVanBan="Thông tư tốc độ",
        ngayBanHanh=date(2019, 7, 12),
        ngayHieuLuc=date(2020, 1, 15),
        coQuanBanHanh="Bộ GTVT",
        loaiVanBan="Thông tư",
    )


def test_chunk_by_dieu():
    """Văn bản có 'Điều N.' → mỗi Điều thành 1 chunk, metadata dieu đúng."""
    text = (
        "Điều 8. Tốc độ tối đa cho phép\n"
        "1. Trong khu vực đông dân cư:\n"
        "a) Xe máy: 40 km/h\n"
        "b) Ô tô: 60 km/h\n"
        "2. Ngoài khu vực đông dân cư: 80 km/h\n\n"
        "Điều 9. Khoảng cách an toàn\n"
        "1. Khi trời khô ráo, tốc độ 60 km/h: khoảng cách tối thiểu 35m.\n"
    )
    chunks = VietnameseLawChunker().chunk_document(text, _meta())

    assert len(chunks) == 2
    assert chunks[0].metadata.dieu == "Điều 8"
    assert chunks[1].metadata.dieu == "Điều 9"
    # Khoản được trích ra từ nội dung Điều 8
    assert "1" in chunks[0].metadata.khoan
    # Metadata văn bản giữ nguyên trên từng chunk
    assert chunks[0].metadata.soHieu == "31/2019/TT-BGTVT"


def test_fallback_no_dieu():
    """Không có 'Điều' (phụ lục/bảng) → cắt theo kích thước, dieu = None."""
    chunker = VietnameseLawChunker(chunk_size=50, chunk_overlap=10, max_chunk_size=80)
    text = "Phụ lục I: Bảng mức phạt vi phạm hành chính. " * 10
    chunks = chunker.chunk_document(text, _meta("100/2019"))

    assert len(chunks) > 1
    assert all(c.metadata.dieu is None for c in chunks)


def test_long_dieu_is_split():
    """Điều dài hơn max_chunk_size → bị cắt nhỏ thêm thành nhiều chunk cùng Điều."""
    chunker = VietnameseLawChunker(chunk_size=200, chunk_overlap=20, max_chunk_size=250)
    long_body = "Nội dung khoản rất dài lặp đi lặp lại để vượt ngưỡng. " * 20
    text = f"Điều 5. Quy định chi tiết\n{long_body}"
    chunks = chunker.chunk_document(text, _meta())

    assert len(chunks) >= 2
    # Tất cả các mảnh vẫn thuộc Điều 5
    assert all(c.metadata.dieu == "Điều 5" for c in chunks)


def test_empty_text_no_chunks():
    """Văn bản rỗng → không tạo chunk."""
    chunks = VietnameseLawChunker().chunk_document("   \n  ", _meta())
    assert chunks == []
