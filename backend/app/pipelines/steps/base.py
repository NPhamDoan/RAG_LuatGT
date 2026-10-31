"""Khung QueryStep — mỗi bước mở rộng xử lý câu hỏi là một step module trong thư mục này.

Điểm móc:
- before_retrieval(ctx): sửa câu hỏi / định tuyến trước khi search (vd chuẩn hóa câu không dấu).
- after_answer(ctx):     hậu xử lý câu trả lời (vd kiểm chứng chéo).

`load_steps` nạp động theo tên trong cấu hình QUERY_STEPS — step bật mà không có file
sẽ bị bỏ qua (ghi WARN). Mỗi step tự chứa logic + prompt + config key trong chính file của nó.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.pipelines.context import QueryContext

if TYPE_CHECKING:
    from app.config import Settings
    from app.providers.embedding_provider import EmbeddingProvider
    from app.providers.llm_provider import LLMProvider
    from app.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class StepDeps:
    """Phụ thuộc chung cấp cho mỗi step khi khởi tạo (qua hàm build của step)."""

    settings: "Settings"
    primary_llm: "LLMProvider"
    embedding: "EmbeddingProvider"
    store: "VectorStore"


@runtime_checkable
class QueryStep(Protocol):
    name: str

    async def before_retrieval(self, ctx: QueryContext) -> None: ...
    async def after_answer(self, ctx: QueryContext) -> None: ...


def load_steps(enabled: list[str], deps: StepDeps) -> list[QueryStep]:
    """Nạp động các step theo tên (mỗi tên → app/pipelines/steps/{name}_step.py)."""
    steps: list[QueryStep] = []
    for name in enabled:
        mod_name = f"app.pipelines.steps.{name}_step"
        try:
            module = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            logger.warning("Query step '%s' được bật nhưng %s không tồn tại → bỏ qua.", name, mod_name)
            continue
        steps.append(module.build(deps))
        logger.info("Đã nạp query step: %s", name)
    return steps
