"""Phase 4 — Enrich step (index-time): làm giàu chunk để tăng recall câu đời thường.

Với mỗi Điều luật, dùng LLM sinh phần BỔ SUNG (tóm tắt + từ khóa + câu hỏi đời thường)
mà điều đó trả lời, rồi GẮN vào text-để-embed. Nhờ đó câu hỏi dân dã ("chạy nhanh trong
phố bị phạt sao?") khớp tốt hơn với điều luật văn phong pháp lý.

QUAN TRỌNG: chỉ đổi `ctx.embed_texts` — `chunk.text` gốc giữ nguyên để hiển thị/trích dẫn.
LLM lỗi cho chunk nào → chunk đó giữ text gốc (không chặn cả quá trình index).

File tự chứa prompt + logic (golden rule): không sửa file lõi. Chỉ đặt trên nhánh có Phase 4.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pydantic_settings import BaseSettings

from app.indexing.base import BaseIndexStep, IndexContext, IndexDeps
from app.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

# QUAN TRONG: doc config tu .env qua pydantic (KHONG dung os.getenv — .env khong vao os.environ).
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"  # backend/.env


class _EnrichSettings(BaseSettings):
    """Config riêng cho enrich, đọc từ backend/.env (env vars ưu tiên hơn file)."""

    # Nguồn text enrich: "llm" = gọi LLM (mặc định); "file" = đọc JSONL soạn sẵn
    # (vd nhờ NotebookLM/ChatGPT khi không có API). Dùng "file" để enrich nhanh + không tốn LLM local.
    enrich_source: str = "llm"
    enrich_file: str = ""   # đường dẫn JSONL khi enrich_source=file

    enrich_llm_provider: str = ""
    enrich_llm_model: str = ""
    enrich_llm_api_key: str = ""
    enrich_ollama_base_url: str = "http://localhost:11434"
    enrich_llm_timeout: int = 60
    # Số chunk enrich ĐỒNG THỜI. Ollama CPU nên để thấp (1-2) tránh timeout; Groq cloud có thể cao hơn.
    enrich_concurrency: int = 4
    # (Ollama) Bật suy luận khi enrich? Mặc định False = TẮT → nhanh hơn nhiều với model thinking (qwen3).
    enrich_ollama_think: bool = False

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}

_ENRICH_SYSTEM_PROMPT = (
    "Bạn là công cụ làm giàu dữ liệu cho hệ thống tìm kiếm văn bản luật giao thông Việt Nam. "
    "Cho một đoạn văn bản luật, hãy tạo phần BỔ SUNG giúp TÌM KIẾM tốt hơn, gồm:\n"
    "- Tóm tắt ngắn (1-2 câu) nội dung chính.\n"
    "- Các TỪ KHÓA quan trọng (đối tượng áp dụng, loại xe/người, con số, mức phạt, chủ đề) "
    "KÈM cách gọi dân dã tương ứng.\n"
    "- 3-5 CÂU HỎI đời thường mà đoạn này trả lời (đa dạng cách diễn đạt, cả câu chung lẫn cụ thể).\n\n"
    "QUY TẮC:\n"
    "- CHỈ dựa trên nội dung đoạn được cung cấp, KHÔNG bịa thêm thông tin/điều luật.\n"
    "- Nếu đoạn liệt kê NHIỀU hành vi (điểm a, b, c...), tạo từ khóa + câu hỏi cho TỪNG hành vi, "
    "KHÔNG bỏ sót hành vi phụ (kể cả khi đoạn tập trung chủ yếu vào một hành vi khác).\n"
    "- BẮT BUỘC thêm CÁCH GỌI DÂN DÃ / từ đồng nghĩa cho thuật ngữ pháp lý, ví dụ:\n"
    "  'không chấp hành hiệu lệnh của đèn tín hiệu' → 'vượt đèn đỏ, vượt đèn vàng';\n"
    "  'nồng độ cồn' → 'uống rượu bia lái xe, say xỉn';\n"
    "  'vượt quá tốc độ quy định' → 'chạy quá tốc độ, chạy nhanh';\n"
    "  'đi ngược chiều của đường một chiều' → 'chạy ngược chiều';\n"
    "  'dừng xe, đỗ xe không đúng quy định' → 'đậu xe sai chỗ'.\n"
    "- Trả lời bằng tiếng Việt, ngắn gọn, KHÔNG lặp lại nguyên văn cả đoạn.\n"
    "- Xuất đúng định dạng:\n"
    "TÓM TẮT: ...\n"
    "TỪ KHÓA: ...\n"
    "CÂU HỎI:\n"
    "- ...\n"
    "- ..."
)

# Giới hạn ký tự gửi LLM cho mỗi chunk (tránh prompt quá dài).
_MAX_CHARS = 1500


class _EnrichFileIndex:
    """Nguồn enrich từ file JSONL soạn sẵn (vd NotebookLM).

    JSONL mỗi dòng: {"soHieu": str, "seq": int, "text_goc": str, "enrich": str}.
    - seq: thứ tự chunk trong văn bản (0-based) — khớp thứ tự chunk của cùng hàm chunk.
    - map theo (soHieu, seq); verify text_goc khớp chunk thật để KHÔNG gắn nhầm.
    """

    @classmethod
    def from_map(cls, so_hieu: str, enrich_by_seq: dict[int, str]) -> "_EnrichFileIndex":
        """Dựng trực tiếp từ map (seq -> enrich) cho MỘT văn bản (form Admin manual).

        Không đọc đĩa; text_goc để rỗng (bỏ verify, vì nguồn là file người dùng vừa add).
        """
        obj = cls.__new__(cls)
        obj._rows = {
            (so_hieu, int(seq)): {"text_goc": "", "enrich": (val or "").strip()}
            for seq, val in enrich_by_seq.items()
        }
        logger.info("Nạp enrich (map) cho %s: %d dòng", so_hieu, len(obj._rows))
        return obj

    def __init__(self, path: Path):
        # key (soHieu, seq) -> {"text_goc", "enrich"}
        self._rows: dict[tuple[str, int], dict] = {}
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning("enrich file dòng %d không parse được JSON: %s", line_no, exc)
                    continue
                key = (str(row.get("soHieu", "")), int(row.get("seq", -1)))
                self._rows[key] = {
                    "text_goc": row.get("text_goc", ""),
                    "enrich": (row.get("enrich") or "").strip(),
                }
        logger.info("Nạp enrich file: %d dòng từ %s", len(self._rows), path)

    def enrich_for(self, chunks: list) -> list:
        """Trả list enrich text song song chunks (giống output LLM).

        - Không có dòng khớp (soHieu, seq) → "" (giữ text gốc, đếm 'empty').
        - text_goc lệch chunk thật → cảnh báo nhưng vẫn dùng enrich (chỉ cảnh báo lệch).
        """
        out: list = []
        # seq tính RIÊNG theo soHieu (một lần process_document chỉ 1 soHieu, nhưng vẫn an toàn).
        seq_by_so_hieu: dict[str, int] = {}
        for c in chunks:
            so_hieu = c.metadata.soHieu
            seq = seq_by_so_hieu.get(so_hieu, 0)
            seq_by_so_hieu[so_hieu] = seq + 1

            row = self._rows.get((so_hieu, seq))
            if row is None:
                out.append("")
                continue
            # Verify text khớp (so sánh phần đầu để tránh nhiễu khoảng trắng).
            if row["text_goc"] and not _text_matches(row["text_goc"], c.text):
                logger.warning(
                    "enrich file: text_goc LỆCH tại (%s, seq=%d) → vẫn dùng enrich, kiểm tra lại export.",
                    so_hieu, seq,
                )
            out.append(row["enrich"])
        return out


def _text_matches(a: str, b: str) -> bool:
    """So khớp 'mềm' 120 ký tự đầu (bỏ khoảng trắng thừa) để verify đúng chunk."""
    norm = lambda s: " ".join(s.split())[:120]
    return norm(a) == norm(b)


class EnrichStep(BaseIndexStep):
    name = "enrich"

    def __init__(
        self,
        llm: LLMProvider | None = None,
        concurrency: int = 4,
        model: str = "",
        file_index: "_EnrichFileIndex | None" = None,
    ):
        self._llm = llm
        self._concurrency = max(1, concurrency)
        self._model = model
        # Khi set → lấy enrich từ file thay vì gọi LLM (nguồn "file").
        self._file_index = file_index

    def manifest_info(self) -> dict:
        """Lộ model/nguồn enrich để ghi vào seed manifest (hiển thị ở Admin)."""
        if self._file_index is not None:
            return {"enrich_model": self._model or "file (manual)", "enrich_source": "file"}
        return {"enrich_model": self._model, "enrich_source": "llm"} if self._model else {}

    async def process(self, ctx: IndexContext) -> None:
        if not ctx.chunks:
            return

        total = len(ctx.chunks)

        # Nguồn FILE: lấy enrich text từ JSONL soạn sẵn (không gọi LLM). Phần ghép +
        # đếm bên dưới DÙNG CHUNG với nguồn LLM → kết quả store/embed giống hệt.
        if self._file_index is not None:
            results = self._file_index.enrich_for(ctx.chunks)
            self._apply_results(ctx, results, total)
            return

        # Giới hạn số request đồng thời: bắn HẾT cùng lúc sẽ làm quá tải LLM
        # (Ollama CPU treo → timeout; Groq → 429 rate limit).
        sem = asyncio.Semaphore(self._concurrency)
        done = 0

        async def _guarded(text: str):
            nonlocal done
            async with sem:
                try:
                    res = await self._enrich_one(text)
                except Exception as exc:  # gom lỗi, không chặn cả mẻ
                    res = exc
            done += 1
            # Enrich lâu → log tiến độ để theo dõi.
            logger.info("Enrich tiến độ: %d/%d chunk.", done, total)
            return res

        results = await asyncio.gather(*[_guarded(c.text) for c in ctx.chunks])
        self._apply_results(ctx, results, total)

    def _apply_results(self, ctx: IndexContext, results: list, total: int) -> None:
        """Ghép enrich vào embed_texts + đếm. DÙNG CHUNG cho nguồn llm lẫn file."""
        enriched = 0
        failed = 0
        empty = 0
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                failed += 1
                # Log kèm LOẠI lỗi (timeout thường có message rỗng) để dễ chẩn đoán.
                logger.warning(
                    "Enrich lỗi chunk %d: %s: %s → giữ text gốc.", i, type(res).__name__, res
                )
                continue
            if not res:
                empty += 1
                continue
            ctx.embed_texts[i] = f"{ctx.chunks[i].text}\n\n[Bổ sung tìm kiếm]\n{res}"
            enriched += 1

        # Cảnh báo nếu số chunk enrich thành công KHÁC tổng số chunk (prompt).
        if enriched < total:
            logger.warning(
                "Enrich: CHỈ %d/%d chunk được làm giàu (%d lỗi, %d rỗng) → %d chunk giữ text gốc.",
                enriched, total, failed, empty, total - enriched,
            )
        else:
            logger.info(
                "Enrich: %d/%d chunk được làm giàu (concurrency=%d).",
                enriched, total, self._concurrency,
            )

    async def _enrich_one(self, text: str) -> str:
        prompt = f"ĐOẠN VĂN BẢN LUẬT:\n{text[:_MAX_CHARS]}\n\nSinh phần bổ sung tìm kiếm:"
        response = await self._llm.generate(prompt=prompt, system_prompt=_ENRICH_SYSTEM_PROMPT)
        return response.content.strip()


def build(deps: IndexDeps) -> EnrichStep:
    """Chọn LLM cho enrich. Kích hoạt step: INDEX_STEPS=enrich trong .env.

    Mặc định dùng LLM synthesis chính (deps.primary_llm). Muốn dùng LLM RIÊNG cho enrich
    (vd chạy Ollama local để đỡ tốn/đỡ rate-limit Groq khi index nhiều chunk), đặt env:
      ENRICH_LLM_PROVIDER    = groq | ollama       (bỏ trống = dùng LLM chính)
      ENRICH_LLM_MODEL       = tên model (vd qwen3:8b / openai/gpt-oss-20b)
      ENRICH_LLM_API_KEY     = (groq) key riêng; bỏ trống thì dùng PRIMARY_LLM_API_KEY
      ENRICH_OLLAMA_BASE_URL = (ollama) mặc định http://localhost:11434
      ENRICH_LLM_TIMEOUT     = giây (mặc định 60)
    """
    cfg = _EnrichSettings()

    # Nguồn FILE: enrich lấy từ JSONL soạn sẵn (NotebookLM...), KHÔNG gọi LLM.
    if cfg.enrich_source.strip().lower() == "file":
        if not cfg.enrich_file.strip():
            raise ValueError("ENRICH_SOURCE=file nhưng ENRICH_FILE trống (đường dẫn JSONL).")
        file_path = Path(cfg.enrich_file.strip())
        if not file_path.is_absolute():
            file_path = _ENV_FILE.parent.parent / file_path  # tương đối so với gốc repo
        if not file_path.is_file():
            raise FileNotFoundError(f"Không thấy ENRICH_FILE: {file_path}")
        logger.info("Enrich nguồn FILE: %s", file_path)
        return EnrichStep(
            concurrency=cfg.enrich_concurrency,
            model="file (manual)",
            file_index=_EnrichFileIndex(file_path),
        )

    return build_auto(deps)


def build_auto(deps: IndexDeps) -> EnrichStep:
    """Enrich bằng LLM (chế độ 'auto'). LLM theo ENRICH_LLM_PROVIDER; trống = LLM chính.

    Dùng cho: CLI seed_data (--enrich auto) và form Admin (radio 'auto').
    """
    cfg = _EnrichSettings()
    provider = cfg.enrich_llm_provider.strip().lower()
    if not provider:
        primary_model = getattr(deps.settings, "primary_llm_provider", "") or "primary"
        return EnrichStep(deps.primary_llm, cfg.enrich_concurrency, model=primary_model)

    model = cfg.enrich_llm_model.strip()
    timeout = cfg.enrich_llm_timeout

    if provider == "groq":
        from app.providers.groq_provider import GroqProvider

        api_key = cfg.enrich_llm_api_key.strip() or getattr(
            deps.settings, "primary_llm_api_key", ""
        )
        resolved_model = model or "openai/gpt-oss-20b"
        llm: LLMProvider = GroqProvider(api_key=api_key, model=resolved_model, timeout=timeout)
    elif provider == "ollama":
        from app.providers.ollama_provider import OllamaProvider

        base_url = cfg.enrich_ollama_base_url.strip() or "http://localhost:11434"
        resolved_model = model or "qwen3:8b"
        llm = OllamaProvider(
            model=resolved_model, base_url=base_url, timeout=timeout,
            think=cfg.enrich_ollama_think,
        )
    else:
        logger.warning(
            "ENRICH_LLM_PROVIDER='%s' không hỗ trợ (groq|ollama) → dùng LLM chính.", provider
        )
        primary_model = getattr(deps.settings, "primary_llm_provider", "") or "primary"
        return EnrichStep(deps.primary_llm, cfg.enrich_concurrency, model=primary_model)

    logger.info(
        "Enrich dùng LLM riêng: provider=%s, model=%s, concurrency=%d",
        provider, resolved_model, cfg.enrich_concurrency,
    )
    return EnrichStep(llm, cfg.enrich_concurrency, model=resolved_model)


def build_manual(so_hieu: str, enrich_by_seq: dict[int, str]) -> EnrichStep:
    """Enrich từ map (seq -> text) do người dùng cung cấp (form Admin 'manual')."""
    return EnrichStep(
        model="file (manual)",
        file_index=_EnrichFileIndex.from_map(so_hieu, enrich_by_seq),
    )
