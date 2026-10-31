"""Configuration module — đọc .env, cung cấp Settings singleton."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@dataclass
class LLMChoice:
    """Cấu hình đã phân giải cho MỘT provider (dùng bởi llm_factory)."""

    kind: str            # groq | mistral | cohere | gemini | ollama
    model: str
    api_key: str = ""
    base_url: str = ""
    timeout: int = 30
    max_tokens: int = 2048
    reasoning_effort: str | None = None
    think: bool | None = None


class Settings(BaseSettings):
    """Application settings loaded from .env."""

    # ===== LLM MODEL CATALOG =====
    # Khai báo sẵn key + model cho MỖI provider (điền 1 lần). Muốn đổi LLM cho một vai trò
    # chỉ cần sửa PRIMARY_LLM_PROVIDER / VERIFY_LLM_PROVIDER ở dưới — không phải đổi model/key.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    # Groq gpt-oss/qwen3 là model REASONING: "low" giảm token suy luận (tránh ăn hết max_tokens
    # → content rỗng); "medium/high" chính xác hơn nhưng tốn token. "" = để model tự quyết.
    groq_reasoning_effort: str = "medium"

    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    cohere_api_key: str = ""
    cohere_model: str = "command-r-08-2024"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout: int = 180   # Ollama chạy CPU thường chậm → timeout riêng, cao hơn cloud
    ollama_think: bool = False  # Tắt suy luận ẩn của qwen3 để tránh timeout trên CPU

    # ===== Tinh chung cho LLM cloud =====
    llm_max_tokens: int = 3500  # reasoning model cần đủ token suy luận + trả lời; xem note .env
    llm_timeout: int = 30       # timeout cho provider cloud (Ollama dùng ollama_timeout)

    # ===== Chọn provider cho từng vai trò (chỉ điền tên) =====
    primary_llm_provider: str = "groq"    # groq | mistral | cohere | gemini | ollama
    verify_llm_provider: str = "gemini"   # gemini | groq | mistral | cohere | ollama

    # ===== Auth admin (chỉ mật khẩu) =====
    # Hash PBKDF2 của mật khẩu admin. TRỐNG = TẮT auth (route ghi mở công khai — chỉ dùng khi dev).
    # Tạo hash: python -m app.api.auth "mat_khau_cua_ban"
    admin_password_hash: str = ""
    auth_secret_key: str = "change-me-doi-thanh-chuoi-ngau-nhien-dai"  # ký token; PHẢI đổi khi deploy
    auth_token_ttl: int = 28800   # thời hạn token (giây), mặc định 8 giờ

    # Embedding
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_dimension: int = 1024

    # ChromaDB
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "luat_giao_thong"

    # Query
    retrieval_top_k: int = 8
    similarity_threshold_min: float = 0.3
    similarity_threshold_confident: float = 0.5
    confidence_high_threshold: float = 0.8

    # Kiến trúc module/plugin — chọn cách tìm kiếm + các bước mở rộng qua .env.
    retrieval_strategy: str = "vector"   # vector (cosine) | hybrid (vector + BM25 + RRF)
    query_steps: str = ""                # CSV query step, vd "normalize,verify"
    index_steps: str = ""                # CSV index step (lúc lập chỉ mục), vd "enrich"

    # Synthesis limits
    synthesis_max_chunks: int = 6
    synthesis_max_chars_per_chunk: int = 5000
    synthesis_prompt: str = "full"  # full | simple

    # File Upload
    max_file_size_mb: int = 50

    # Logging
    log_level: str = "INFO"
    log_file: str = ""
    # Log trace theo TỪNG phase (CSV). Giá trị: "all" | "none"/"" | danh sách tên phase.
    # Tên phase: pipeline (lõi retrieval/gating), normalize, enrich, verify, help_intent...
    # Vd LOG_PHASES=pipeline,normalize  → chỉ log 2 phase đó. Mặc định "all".
    log_phases: str = "all"

    @property
    def query_steps_list(self) -> list[str]:
        """Danh sách query step bật, parse từ CSV `query_steps`."""
        return [s.strip() for s in self.query_steps.split(",") if s.strip()]

    @property
    def index_steps_list(self) -> list[str]:
        """Danh sách index step bật, parse từ CSV `index_steps`."""
        return [s.strip() for s in self.index_steps.split(",") if s.strip()]

    @property
    def log_phases_set(self) -> set[str]:
        """Tập phase được bật log trace (lowercase). Chứa 'all' = bật hết."""
        return {s.strip().lower() for s in self.log_phases.split(",") if s.strip()}

    def resolve_llm(self, provider: str) -> LLMChoice:
        """Phân giải tên provider → LLMChoice (lấy key/model từ catalog).

        Dùng cho mọi vai trò (primary/verify): factory chỉ cần tên provider.
        """
        p = (provider or "").strip().lower()
        if p == "groq":
            return LLMChoice(
                kind="groq", model=self.groq_model, api_key=self.groq_api_key,
                timeout=self.llm_timeout, max_tokens=self.llm_max_tokens,
                reasoning_effort=self.groq_reasoning_effort or None,
            )
        if p == "mistral":
            return LLMChoice(
                kind="mistral", model=self.mistral_model, api_key=self.mistral_api_key,
                timeout=self.llm_timeout, max_tokens=self.llm_max_tokens,
            )
        if p == "cohere":
            return LLMChoice(
                kind="cohere", model=self.cohere_model, api_key=self.cohere_api_key,
                timeout=self.llm_timeout, max_tokens=self.llm_max_tokens,
            )
        if p == "gemini":
            return LLMChoice(
                kind="gemini", model=self.gemini_model, api_key=self.gemini_api_key,
                timeout=self.llm_timeout, max_tokens=self.llm_max_tokens,
            )
        if p == "ollama":
            return LLMChoice(
                kind="ollama", model=self.ollama_model, base_url=self.ollama_base_url,
                timeout=self.ollama_timeout, max_tokens=self.llm_max_tokens,
                think=self.ollama_think,
            )
        raise ValueError(
            f"Provider LLM '{provider}' không hỗ trợ. "
            "Dùng: groq | mistral | cohere | gemini | ollama."
        )

    @property
    def chroma_persist_path(self) -> str:
        """Đường dẫn tuyệt đối tới thư mục ChromaDB."""
        p = Path(self.chroma_persist_directory)
        if not p.is_absolute():
            p = _PROJECT_ROOT / p
        return str(p.resolve())

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        # Bỏ qua env lạ (vd ENRICH_LLM_* do enrich_step đọc riêng) thay vì báo lỗi.
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Cached Settings singleton."""
    return Settings()
