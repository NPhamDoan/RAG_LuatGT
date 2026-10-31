"""QueryContext — túi dữ liệu đi xuyên các step của query pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.schemas import KetQuaTraLoi
from app.storage.vector_store import SearchResult


@dataclass
class QueryContext:
    """Trạng thái dùng chung khi xử lý một câu hỏi.

    Các step đọc/ghi vào đây. Lõi orchestrator điều phối:
    before_retrieval → embed → retrieval → answer → after_answer.
    """

    cau_hoi: str
    query_vector: list[float] | None = None
    results: list[SearchResult] = field(default_factory=list)
    ket_qua: KetQuaTraLoi | None = None
    # Step có thể set True + gán ket_qua để trả sớm (vd định tuyến help-intent).
    short_circuit: bool = False
