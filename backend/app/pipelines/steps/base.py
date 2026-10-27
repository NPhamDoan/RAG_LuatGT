"""Khung QueryStep — mỗi phase (3/4/5) là một step module trong thư mục này.

Điểm móc:
- before_retrieval(ctx): sửa câu hỏi / định tuyến trước khi search (Phase 3 normalize, Phase 5 help-intent).
- after_answer(ctx):     hậu xử lý câu trả lời (Phase 4 cross-verify).

Giao hàng: chỉ copy file step của phase đã bán. `load_steps` nạp động — step nào
bật trong config mà file KHÔNG có sẽ bị bỏ qua (code vắng = không chạy).

Quy ước để git merge không đụng nhau: mỗi step tự chứa logic + prompt + config key
trong CHÍNH file của nó, không sửa file lõi dùng chung.
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
    verify_llm: "LLMProvider | None" = None


@runtime_checkable
class QueryStep(Protocol):
    name: str

    async def before_retrieval(self, ctx: QueryContext) -> None: ...
    async def after_answer(self, ctx: QueryContext) -> None: ...


class BaseStep:
    """Base tiện lợi: step chỉ cần override hook nó dùng."""

    name = "base"

    async def before_retrieval(self, ctx: QueryContext) -> None:  # noqa: D401
        return None

    async def after_answer(self, ctx: QueryContext) -> None:
        return None


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
