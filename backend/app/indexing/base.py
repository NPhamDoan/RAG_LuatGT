"""Khung IndexStep — mỗi bước lập chỉ mục (vd enrich) là một step module ở đây.

Chạy giữa bước chunk và embed trong document_pipeline. Điểm móc:
- process(ctx): sửa `ctx.embed_texts` (text dùng để EMBED).

QUAN TRỌNG: step CHỈ đổi text-để-embed. `chunk.text` gốc vẫn được lưu (store) để
hiển thị/trích dẫn — enrich giúp tăng recall mà không làm bẩn nội dung luật hiển thị.

Nạp động qua `load_index_steps` (config `INDEX_STEPS`). Step vắng file → bỏ qua.
Mỗi step tự chứa logic + prompt + config key, không sửa file lõi.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.chunking.chunker import Chunk

if TYPE_CHECKING:
    from app.config import Settings
    from app.providers.embedding_provider import EmbeddingProvider
    from app.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class IndexContext:
    """Dữ liệu index đi xuyên các step.

    - ``chunks``: chunk gốc (text sẽ được STORE để hiển thị) — step KHÔNG nên đổi.
    - ``embed_texts``: text dùng để EMBED, song song ``chunks``. Mặc định = chunk.text.
      Step enrich sửa list này để cải thiện recall.
    """

    chunks: list[Chunk]
    embed_texts: list[str]


@dataclass
class IndexDeps:
    """Phụ thuộc cấp cho mỗi index step (qua hàm build của step)."""

    settings: "Settings"
    primary_llm: "LLMProvider"
    embedding: "EmbeddingProvider"


@runtime_checkable
class IndexStep(Protocol):
    name: str

    async def process(self, ctx: IndexContext) -> None: ...

    def manifest_info(self) -> dict: ...


class BaseIndexStep:
    """Base tiện lợi."""

    name = "base"

    async def process(self, ctx: IndexContext) -> None:
        return None

    def manifest_info(self) -> dict:
        """Thông tin step tự khai báo để ghi vào seed manifest (vd model dùng).

        Mặc định rỗng. Step override nếu muốn lộ chi tiết — lõi gộp vào manifest
        mà KHÔNG cần biết step cụ thể là gì (lõi không phụ thuộc step).
        """
        return {}


def load_index_steps(enabled: list[str], deps: IndexDeps) -> list[IndexStep]:
    """Nạp động index step theo tên (mỗi tên → app/indexing/{name}_step.py)."""
    steps: list[IndexStep] = []
    for name in enabled:
        mod_name = f"app.indexing.{name}_step"
        try:
            module = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            logger.warning("Index step '%s' được bật nhưng %s không tồn tại → bỏ qua.", name, mod_name)
            continue
        steps.append(module.build(deps))
        logger.info("Đã nạp index step: %s", name)
    return steps
