"""Vietnamese Law Chunker — cắt văn bản luật giao thông theo Điều.

Chiến lược:
- Có "Điều N." hoặc "Điều N:" ở đầu dòng → cắt theo ranh giới Điều.
- Không có Điều (thông tư dạng bảng/phụ lục) → cắt theo kích thước + overlap.
- Điều quá dài (> max_chunk_size) → cắt nhỏ thêm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ChunkMetadata:
    """Metadata đính kèm mỗi chunk."""

    soHieu: str
    tenVanBan: str
    dieu: str | None = None
    khoan: list[str] = field(default_factory=list)
    muc: list[str] = field(default_factory=list)   # điểm a/b/c... trong Điều
    ngayBanHanh: date | None = None
    ngayHieuLuc: date | None = None
    coQuanBanHanh: str = ""
    loaiVanBan: str = ""


@dataclass
class Chunk:
    """Một chunk văn bản + metadata."""

    text: str
    metadata: ChunkMetadata


@dataclass
class DocumentMetadata:
    """Metadata đầu vào khi nạp văn bản."""

    soHieu: str
    tenVanBan: str
    ngayBanHanh: date
    ngayHieuLuc: date
    coQuanBanHanh: str = ""
    loaiVanBan: str = ""


class VietnameseLawChunker:
    """Cắt văn bản luật thành chunk theo Điều."""

    # Pattern: đầu dòng, optional whitespace, "Điều" + số + dấu . hoặc :
    DIEU_BOUNDARY = re.compile(r"^[ \t]*Điều\s+(\d+)\s*[.:]", re.MULTILINE)
    KHOAN_PATTERN = re.compile(r"(?:^|\n)\s*(\d+)\.\s")
    MUC_PATTERN = re.compile(r"(?:^|\n)\s*([a-zA-Zđ])\)\s")   # điểm a) b) c)...

    def __init__(
        self,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
        max_chunk_size: int = 1800,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_chunk_size = max_chunk_size

    def chunk_document(self, text: str, base_metadata: DocumentMetadata) -> list[Chunk]:
        """Tách văn bản thành chunks.

        - Có Điều → cắt theo Điều.
        - Không có Điều → cắt theo kích thước.
        """
        matches = list(self.DIEU_BOUNDARY.finditer(text))

        if not matches:
            return self._chunks_by_size(text, base_metadata, dieu=None)

        chunks: list[Chunk] = []

        # Phần mở đầu (trước Điều đầu tiên)
        preamble = text[: matches[0].start()]
        chunks.extend(self._chunks_by_size(preamble, base_metadata, dieu=None))

        # Cắt theo Điều
        for i, match in enumerate(matches):
            dieu_number = match.group(1)
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            dieu_text = text[start:end]
            # Tiêu đề Điều (dòng đầu) chứa LOẠI XE áp dụng (vd "Điều 7. ... xe mô tô, xe gắn máy").
            # Gắn vào mỗi sub-chunk để KHÔNG mất ngữ cảnh loại xe khi Điều bị cắt nhỏ theo khoản.
            dieu_header = dieu_text.strip().split("\n", 1)[0].strip()
            chunks.extend(
                self._chunks_by_size(
                    dieu_text, base_metadata, dieu=f"Điều {dieu_number}", header=dieu_header
                )
            )

        return chunks

    def _chunks_by_size(
        self, text: str, base_metadata: DocumentMetadata, dieu: str | None, header: str = ""
    ) -> list[Chunk]:
        """Nếu text ngắn → 1 chunk. Nếu dài → cắt nhỏ (gắn tiêu đề Điều vào từng chunk)."""
        stripped = text.strip()
        if not stripped:
            return []

        if len(stripped) <= self.max_chunk_size:
            return [Chunk(text=stripped, metadata=self._build_meta(base_metadata, dieu, stripped))]

        parts = self._split_by_size(stripped)
        chunks: list[Chunk] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # Chunk không bắt đầu bằng tiêu đề Điều → prepend để giữ ngữ cảnh loại xe/Điều.
            if header and not p.startswith(header[:20]):
                p = f"{header}\n{p}"
            chunks.append(Chunk(text=p, metadata=self._build_meta(base_metadata, dieu, p)))
        return chunks

    def _split_by_size(self, text: str) -> list[str]:
        """Cắt text dài thành ~chunk_size, ưu tiên ngắt ở dòng/khoảng trắng."""
        size = self.chunk_size
        overlap = self.chunk_overlap
        n = len(text)
        chunks: list[str] = []
        start = 0

        while start < n:
            end = min(start + size, n)
            if end < n:
                # Tìm điểm ngắt tốt
                window = text.rfind("\n", start + size // 2, end)
                if window == -1:
                    window = text.rfind(" ", start + size // 2, end)
                if window > start:
                    end = window

            piece = text[start:end].strip()
            if piece:
                chunks.append(piece)

            # Bước tiếp: lùi overlap
            start = end - overlap if end < n else n

        return chunks

    def _build_meta(
        self, base: DocumentMetadata, dieu: str | None, text: str
    ) -> ChunkMetadata:
        """Tạo metadata cho chunk, tự detect Khoản + Mục (điểm a/b/c)."""
        khoan = [m.group(1) for m in self.KHOAN_PATTERN.finditer(text)]
        muc = [m.group(1) for m in self.MUC_PATTERN.finditer(text)]
        return ChunkMetadata(
            soHieu=base.soHieu,
            tenVanBan=base.tenVanBan,
            dieu=dieu,
            khoan=khoan,
            muc=muc,
            ngayBanHanh=base.ngayBanHanh,
            ngayHieuLuc=base.ngayHieuLuc,
            coQuanBanHanh=base.coQuanBanHanh,
            loaiVanBan=base.loaiVanBan,
        )
