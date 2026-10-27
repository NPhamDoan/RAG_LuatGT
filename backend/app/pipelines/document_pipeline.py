"""Document Pipeline — parse → chunk → embed → store."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime

import pymupdf as fitz

from app.chunking.chunker import Chunk, DocumentMetadata, VietnameseLawChunker
from app.config import get_settings
from app.indexing.base import IndexContext, IndexStep
from app.models.schemas import DocumentMetadataInput, IndexingResult
from app.providers.embedding_provider import EmbeddingProvider
from app.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


def _git_info() -> dict:
    """Lấy nhánh + commit hiện tại (để truy ngược data thuộc delivery nào).

    An toàn: không có git / không phải repo → trả rỗng, không làm hỏng index.
    """
    def _run(args: list[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args], capture_output=True, text=True, timeout=5
            )
            return out.stdout.strip() if out.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""

    return {
        "git_branch": _run(["rev-parse", "--abbrev-ref", "HEAD"]),
        "git_commit": _run(["rev-parse", "--short", "HEAD"]),
    }


class DocumentPipelineError(Exception):
    """Lỗi trong quá trình nạp văn bản."""


class DuplicateDocumentError(Exception):
    """Văn bản đã tồn tại."""
    def __init__(self, so_hieu: str):
        super().__init__(f"Văn bản '{so_hieu}' đã tồn tại.")
        self.so_hieu = so_hieu


class DocumentPipeline:
    """Pipeline: parse → chunk → embed → store."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        max_file_size_mb: int | None = None,
        index_steps: list[IndexStep] | None = None,
    ):
        self._embedding = embedding_provider
        self._store = vector_store
        self._chunker = VietnameseLawChunker()
        self._index_steps = index_steps or []
        self._last_steps: list[IndexStep] = self._index_steps  # step dùng ở lần nạp gần nhất
        if max_file_size_mb is None:
            max_file_size_mb = get_settings().max_file_size_mb
        self._max_file_size_bytes = max_file_size_mb * 1024 * 1024

    async def process_document(
        self,
        file_content: bytes,
        filename: str,
        metadata: DocumentMetadataInput,
        *,
        replace: bool = False,
        index_steps_override: list[IndexStep] | None = None,
    ) -> IndexingResult:
        """Full pipeline: parse → validate → chunk → embed → store.

        index_steps_override: nếu truyền (kể cả list rỗng) → DÙNG danh sách step này
        cho lần nạp này thay cho self._index_steps. Form Admin dùng để chọn enrich
        auto/manual/none per-request; None = dùng step mặc định (seed/CLI).
        """

        logger.info(
            "Nhận upload: file=%s, soHieu=%s, size=%.1fKB",
            filename, metadata.soHieu, len(file_content) / 1024,
        )

        # 1. Validate size
        if len(file_content) > self._max_file_size_bytes:
            limit_mb = self._max_file_size_bytes / 1024 / 1024
            raise DocumentPipelineError(
                f"File vượt {limit_mb:.0f}MB ({len(file_content) / 1024 / 1024:.1f}MB)."
            )

        # 2. Validate format
        ext: str = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("pdf", "txt"):
            raise DocumentPipelineError(f"Định dạng '{ext}' không hỗ trợ. Chỉ PDF hoặc TXT.")

        # 3. Check duplicate
        exists: bool = await self._store.exists(metadata.soHieu)
        if exists and not replace:
            raise DuplicateDocumentError(metadata.soHieu)

        # 4. Parse
        raw_text: str = self._parse(file_content, ext)
        if not raw_text.strip():
            raise DocumentPipelineError("Không extract được text (có thể là PDF scan).")

        # 5. Chunk
        base_meta: DocumentMetadata = DocumentMetadata(
            soHieu=metadata.soHieu,
            tenVanBan=metadata.tenVanBan,
            ngayBanHanh=metadata.ngayBanHanh,
            ngayHieuLuc=metadata.ngayHieuLuc,
            coQuanBanHanh=metadata.coQuanBanHanh,
            loaiVanBan=metadata.loaiVanBan,
        )
        chunks: list[Chunk] = self._chunker.chunk_document(raw_text, base_meta)
        if not chunks:
            raise DocumentPipelineError("Không tạo được chunk từ văn bản.")
        logger.info("Đã chunk '%s': %d chunk.", metadata.soHieu, len(chunks))

        # 6. Index steps (Phase 4 enrich...) — chỉ sửa text-để-embed, chunk.text gốc giữ nguyên.
        #    override (từ form Admin: auto/manual/none) ưu tiên hơn step mặc định.
        steps = self._index_steps if index_steps_override is None else index_steps_override
        self._last_steps = steps  # để _seed_metadata ghi nhãn đúng lần nạp này
        index_ctx = IndexContext(chunks=chunks, embed_texts=[c.text for c in chunks])
        if steps:
            logger.info("Chạy %d index step trên %d chunk...", len(steps), len(chunks))
        for step in steps:
            await step.process(index_ctx)

        # 7. Embed (dùng embed_texts đã qua index steps)
        logger.info(
            "Bắt đầu embed %d chunk (lần đầu sẽ chậm do nạp model ~2GB)...", len(chunks)
        )
        vectors: list[list[float]] = await self._embedding.embed_batch(index_ctx.embed_texts)
        logger.info("Embed xong: %d vector.", len(vectors))

        # 8. Replace nếu cần
        if exists and replace:
            await self._store.delete_by_so_hieu(metadata.soHieu)

        # 9. Store (chunk.text gốc để hiển thị; vector đã enrich nếu có index step)
        #    Gắn seed info PER-DOCUMENT vào metadata mỗi chunk → Admin hiển thị
        #    "văn bản này nạp kiểu gì" cho TỪNG văn bản.
        await self._store.add_chunks(chunks, vectors, extra_metadata=self._seed_metadata())

        logger.info(
            "Indexed: soHieu=%s, tenVanBan=%s, chunks=%d",
            metadata.soHieu, metadata.tenVanBan, len(chunks),
        )

        return IndexingResult(
            soHieu=metadata.soHieu,
            tenVanBan=metadata.tenVanBan,
            soChunks=len(chunks),
            ngayIndex=datetime.now(),
        )

    def _seed_metadata(self) -> dict:
        """Dựng seed info PER-DOCUMENT để gắn vào metadata mỗi chunk.

        Cho biết VĂN BẢN NÀY nạp kiểu gì: enrich bật/tắt, source/model, retrieval,
        embedding, nhánh/commit, thời điểm. ChromaDB metadata chỉ nhận scalar nên
        list index_steps được nối thành chuỗi.
        """
        settings = get_settings()
        steps = self._last_steps

        step_info: dict = {}
        for step in steps:
            try:
                step_info.update(step.manifest_info())
            except Exception:  # step lỗi khai báo manifest → bỏ qua, không chặn index
                logger.warning("Index step '%s' manifest_info() lỗi.", getattr(step, "name", "?"))

        git = _git_info()
        return {
            "seedVersion": 1,
            "seedAt": datetime.now().isoformat(timespec="seconds"),
            "seedIndexSteps": ",".join(getattr(s, "name", "?") for s in steps),
            "seedEnrichEnabled": any(getattr(s, "name", "") == "enrich" for s in steps),
            "seedEnrichSource": step_info.get("enrich_source", ""),
            "seedEnrichModel": step_info.get("enrich_model", ""),
            "seedRetrieval": settings.retrieval_strategy,
            "seedEmbedding": settings.embedding_model,
            "seedGitBranch": git.get("git_branch", ""),
            "seedGitCommit": git.get("git_commit", ""),
        }

    def chunk_only(
        self, file_content: bytes, filename: str, metadata: DocumentMetadataInput
    ) -> list[Chunk]:
        """Chỉ parse + chunk (KHÔNG embed/store). Dùng cho 'Get chunk' từ PDF chưa nạp.

        Thứ tự chunk ở đây KHỚP với lúc process_document (cùng chunker) → seq nhất quán.
        """
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in ("pdf", "txt"):
            raise DocumentPipelineError(f"Định dạng '{ext}' không hỗ trợ. Chỉ PDF hoặc TXT.")
        raw_text = self._parse(file_content, ext)
        if not raw_text.strip():
            raise DocumentPipelineError("Không extract được text (có thể là PDF scan).")
        base_meta = DocumentMetadata(
            soHieu=metadata.soHieu, tenVanBan=metadata.tenVanBan,
            ngayBanHanh=metadata.ngayBanHanh, ngayHieuLuc=metadata.ngayHieuLuc,
            coQuanBanHanh=metadata.coQuanBanHanh, loaiVanBan=metadata.loaiVanBan,
        )
        chunks = self._chunker.chunk_document(raw_text, base_meta)
        if not chunks:
            raise DocumentPipelineError("Không tạo được chunk từ văn bản.")
        return chunks

    def _parse(self, content: bytes, ext: str) -> str:
        """Parse file → plain text."""
        if ext == "pdf":
            return self._parse_pdf(content)
        return content.decode("utf-8", errors="replace")

    def _parse_pdf(self, content: bytes) -> str:
        """Extract text từ PDF bằng PyMuPDF."""
        doc: fitz.Document = fitz.open(stream=content, filetype="pdf")
        try:
            pages: list[str] = [page.get_text() for page in doc]
        finally:
            doc.close()
        return "\n".join(pages)
