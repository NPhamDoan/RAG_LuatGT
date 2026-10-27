"""Query Pipeline — orchestrator mỏng.

Luồng: before_retrieval(steps) → embed → retrieval strategy → answer (gating +
synthesis + fallback) → after_answer(steps).

Lõi này KHÔNG chứa logic riêng của phase nào. Mỗi phase cắm vào qua:
- Retrieval strategy (Phase 1 vector / Phase 2 hybrid) — inject lúc khởi tạo.
- QueryStep (Phase 3/4/5) — danh sách step inject lúc khởi tạo.
Nhờ vậy thêm phase = thêm file module, không sửa file này.
"""

from __future__ import annotations

import logging
from typing import Literal

from app.config import Settings, get_settings
from app.models.schemas import KetQuaTraLoi, TrichDan
from app.pipelines.context import QueryContext
from app.pipelines.steps.base import QueryStep
from app.prompts.system_prompts import (
    SIMPLE_SYNTHESIS_SYSTEM_PROMPT,
    SYNTHESIS_SYSTEM_PROMPT,
)
from app.providers.embedding_provider import EmbeddingProvider
from app.providers.llm_provider import LLMProvider
from app.retrieval.base import RetrievalStrategy
from app.storage.vector_store import SearchResult

logger = logging.getLogger(__name__)


class QueryPipeline:
    """Điều phối các bước xử lý câu hỏi. Logic phase nằm ở strategy + steps."""

    def __init__(
        self,
        primary_llm: LLMProvider,
        embedding_provider: EmbeddingProvider,
        retrieval: RetrievalStrategy,
        settings: Settings | None = None,
        steps: list[QueryStep] | None = None,
    ):
        self._llm = primary_llm
        self._embedding = embedding_provider
        self._retrieval = retrieval
        self._settings = settings or get_settings()
        self._steps = steps or []

    def _trace(self, phase: str, msg: str, *args) -> None:
        """Log trace cho một phase cụ thể — chỉ log nếu phase đó được bật (settings.log_phases)."""
        phases = getattr(self._settings, "log_phases_set", {"all"})
        if "all" in phases or phase in phases:
            logger.info("[phase:%s] " + msg, phase, *args)

    async def process_query(self, cau_hoi: str) -> KetQuaTraLoi:
        ctx = QueryContext(cau_hoi=cau_hoi)
        self._trace(
            "pipeline",
            "Query bắt đầu | steps=%s | strategy=%s",
            [s.name for s in self._steps] or "-",
            type(self._retrieval).__name__,
        )

        # Steps trước retrieval (Phase 3 normalize, Phase 5 help-intent...).
        for step in self._steps:
            self._trace(step.name, "→ before_retrieval")
            await step.before_retrieval(ctx)
            if ctx.short_circuit and ctx.ket_qua is not None:
                self._trace(step.name, "↩ short-circuit → trả sớm")
                return ctx.ket_qua

        # Embed + retrieval (strategy quyết định vector hay hybrid).
        self._trace("pipeline", "→ embed + retrieval (top_k=%d)", self._settings.retrieval_top_k)
        ctx.query_vector = await self._embedding.embed_text(ctx.cau_hoi)
        ctx.results = await self._retrieval.search(
            ctx.query_vector, self._settings.retrieval_top_k, ctx.cau_hoi
        )
        self._trace("pipeline", "← retrieval: %d kết quả", len(ctx.results))

        # Lõi Phase 1: gating + synthesis + fallback.
        ctx.ket_qua = await self._answer(ctx.cau_hoi, ctx.results)

        # Steps sau khi có câu trả lời (Phase 4 cross-verify...).
        for step in self._steps:
            self._trace(step.name, "→ after_answer")
            await step.after_answer(ctx)

        self._trace(
            "pipeline",
            "Query xong | doTinCay=%s | trichDan=%d",
            ctx.ket_qua.doTinCay if ctx.ket_qua else "?",
            len(ctx.ket_qua.trichDan) if ctx.ket_qua else 0,
        )
        return ctx.ket_qua

    async def _answer(self, cau_hoi: str, results: list[SearchResult]) -> KetQuaTraLoi:
        """Gating + synthesis + fallback (hành vi Phase 1, giữ nguyên)."""
        if not results:
            self._trace("pipeline", "gating: 0 kết quả → không tìm thấy")
            return self._no_results()

        # Gộp các chunk cùng một (soHieu, Điều) — vốn là các mảnh của MỘT điều bị cắt
        # nhỏ — để tránh trích dẫn trùng. Dùng chung cho cả prompt lẫn citation nên số
        # [n] trong câu trả lời vẫn khớp với chip.
        results = self._dedupe_results(results)

        max_score = max(r.score for r in results)

        if max_score < self._settings.similarity_threshold_min:
            self._trace("pipeline", "gating: max_score=%.3f < min=%.2f → dừng", max_score, self._settings.similarity_threshold_min)
            return self._no_results()

        if max_score < self._settings.similarity_threshold_confident:
            self._trace("pipeline", "gating: max_score=%.3f < confident=%.2f → không đủ liên quan", max_score, self._settings.similarity_threshold_confident)
            return KetQuaTraLoi(
                noiDung="Không tìm thấy văn bản đủ liên quan.",
                trichDan=[],
                doTinCay="thấp",
            )

        do_tin_cay = self._calc_confidence(max_score)
        self._trace("pipeline", "gating: max_score=%.3f → synthesis (%d chunk, độ tin cậy=%s)", max_score, len(results), do_tin_cay)

        try:
            prompt = self._build_synthesis_prompt(cau_hoi, results)
            response = await self._llm.generate(
                prompt=prompt,
                system_prompt=self._get_synthesis_system_prompt(),
            )
            return KetQuaTraLoi(
                noiDung=response.content,
                trichDan=self._build_citations(results),
                doTinCay=do_tin_cay,
            )
        except Exception as exc:
            logger.error(
                "LLM lỗi cho query '%.50s' (%s): %s. Fallback chunk gốc.",
                cau_hoi,
                type(exc).__name__,
                exc,
                exc_info=True,
            )
            return self._fallback(results, do_tin_cay)

    def _get_synthesis_system_prompt(self) -> str:
        """Chọn prompt synthesis theo SYNTHESIS_PROMPT trong .env."""
        prompt_name = self._settings.synthesis_prompt.strip().lower()
        if prompt_name == "simple":
            return SIMPLE_SYNTHESIS_SYSTEM_PROMPT
        if prompt_name == "full":
            return SYNTHESIS_SYSTEM_PROMPT
        raise ValueError(
            f"SYNTHESIS_PROMPT không hợp lệ: {prompt_name!r}; "
            "chỉ hỗ trợ 'full' hoặc 'simple'."
        )

    def _no_results(self) -> KetQuaTraLoi:
        return KetQuaTraLoi(
            noiDung="Không tìm thấy điều khoản phù hợp trong luật giao thông.",
            trichDan=[],
            doTinCay="thấp",
        )

    def _calc_confidence(self, max_score: float) -> Literal["cao", "trung bình", "thấp"]:
        if max_score >= self._settings.confidence_high_threshold:
            return "cao"
        if max_score >= self._settings.similarity_threshold_confident:
            return "trung bình"
        return "thấp"

    def _build_synthesis_prompt(self, cau_hoi: str, results: list[SearchResult]) -> str:
        """Xây prompt: đánh số chunk [1..N] + câu hỏi."""
        max_chunks = self._settings.synthesis_max_chunks
        max_chars = self._settings.synthesis_max_chars_per_chunk
        numbered: list[str] = []

        for i, r in enumerate(results[:max_chunks], 1):
            meta = r.metadata
            header = f"[{i}] {meta.get('tenVanBan', '')} ({meta.get('soHieu', '')})"
            dieu = meta.get("dieu", "")
            if dieu:
                header += f" — {dieu}"
            ngay = meta.get("ngayHieuLuc", "không rõ")
            header += f" — hiệu lực {ngay}"

            text = r.text[:max_chars]
            numbered.append(f"{header}\nNội dung:\n{text}")

        so_doan = len(numbered)
        chunks_text = "\n\n".join(numbered)

        return (
            f"CÂU HỎI CỦA NGƯỜI DÙNG:\n{cau_hoi}\n\n"
            f"CÁC ĐOẠN VĂN BẢN PHÁP LUẬT GIAO THÔNG (đánh số [1]..[{so_doan}]):\n\n"
            f"{chunks_text}\n\n"
            f"YÊU CẦU:\n"
            f"- Trả lời theo 4 mục (Phân tích/Giải pháp/Căn cứ/Lưu ý).\n"
            f"- CHỈ chèn [n] ở mục Giải pháp (CHỈ dùng [1]..[{so_doan}]); các mục khác KHÔNG chèn [n].\n"
            f"- Số Điều trong câu phải TRÙNG số Điều ở tiêu đề đoạn [n] trích; không bịa số Điều.\n"
            f"- Nếu mâu thuẫn giữa Luật và Thông tư, nêu rõ văn bản mới hơn.\n"
            f"- Nếu thiếu căn cứ, nói rõ ở mục Lưu ý."
        )

    def _build_citations(self, results: list[SearchResult]) -> list[TrichDan]:
        """Tạo danh sách trích dẫn từ search results."""
        max_chunks = self._settings.synthesis_max_chunks
        citations: list[TrichDan] = []
        for r in results[:max_chunks]:
            meta = r.metadata
            citations.append(TrichDan(
                soHieu=meta.get("soHieu", ""),
                tenVanBan=meta.get("tenVanBan", ""),
                dieu=meta.get("dieu") or None,
                khoan=meta.get("khoan") or None,
                noiDungDayDu=r.text,
            ))
        return citations

    def _dedupe_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Gộp các mảnh của cùng một Điều thành một kết quả.

        - Key gộp: (soHieu, dieu). Chunk có dieu rỗng (mở đầu/bảng) KHÔNG gộp.
        - Giữ điểm cao nhất trong nhóm; ghép nội dung theo thứ tự tài liệu (theo id);
          gộp danh sách khoản.
        """
        groups: dict[tuple[str, str], list[SearchResult]] = {}
        order: list[tuple[str, str]] = []
        for i, r in enumerate(results):
            so_hieu = r.metadata.get("soHieu", "")
            dieu = r.metadata.get("dieu", "")
            key = (so_hieu, dieu) if dieu else (so_hieu, f"__uniq_{i}")
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(r)

        merged: list[SearchResult] = []
        for key in order:
            items = groups[key]
            if len(items) == 1:
                merged.append(items[0])
                continue
            ordered = sorted(items, key=lambda x: self._chunk_order(x.id))
            base_meta = dict(ordered[0].metadata)
            base_meta["khoan"] = self._merge_khoan(ordered)
            merged.append(SearchResult(
                id=ordered[0].id,
                text="\n\n".join(x.text for x in ordered),
                metadata=base_meta,
                score=max(x.score for x in items),
            ))

        merged.sort(key=lambda r: r.score, reverse=True)
        return merged

    @staticmethod
    def _chunk_order(chunk_id: str) -> int:
        """Thứ tự mảnh trong 1 Điều từ id `{soHieu}__dieu_{N}[__{k}]` (mảnh gốc = 0)."""
        parts = chunk_id.split("__")
        if len(parts) >= 3 and parts[-1].isdigit():
            return int(parts[-1])
        return 0

    @staticmethod
    def _merge_khoan(items: list[SearchResult]) -> str:
        """Gộp các khoản (chuỗi ',') của nhiều mảnh, khử trùng, giữ thứ tự."""
        seen: list[str] = []
        for r in items:
            for k in (r.metadata.get("khoan", "") or "").split(","):
                k = k.strip()
                if k and k not in seen:
                    seen.append(k)
        return ",".join(seen)

    def _fallback(self, results: list[SearchResult], do_tin_cay: str) -> KetQuaTraLoi:
        """Fallback: trả chunk gốc khi LLM lỗi."""
        max_chunks = self._settings.synthesis_max_chunks
        chunks_goc = [r.text for r in results[:max_chunks]]
        trich_dan = self._build_citations(results)
        return KetQuaTraLoi(
            noiDung="LLM tạm thời không khả dụng. Dưới đây là các điều khoản liên quan:",
            trichDan=trich_dan,
            doTinCay=do_tin_cay,
            chunksGoc=chunks_goc,
        )
