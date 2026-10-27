"""Test khung index-step + DocumentPipeline.

Kiểm: không có index step → hành vi Phase 1 y nguyên (embed chunk.text, store chunk.text).
Có index step → embed dùng text đã enrich, NHƯNG store vẫn là chunk.text gốc.
"""

from datetime import date

from app.indexing.base import IndexContext, IndexDeps, load_index_steps
from app.models.schemas import DocumentMetadataInput
from app.pipelines.document_pipeline import DocumentPipeline
from tests.fakes import FakeEmbedding, FakeIndexStore, run

_TXT = (
    "Điều 1. Phạm vi điều chỉnh\n"
    "Luật này quy định về trật tự, an toàn giao thông đường bộ.\n\n"
    "Điều 2. Giải thích từ ngữ\n"
    "Trong luật này, các từ ngữ dưới đây được hiểu như sau.\n"
).encode("utf-8")


def _meta():
    return DocumentMetadataInput(
        soHieu="36/2024/QH15",
        tenVanBan="Luật TTATGT",
        ngayBanHanh=date(2024, 6, 27),
        ngayHieuLuc=date(2025, 1, 1),
    )


class _AppendStep:
    """Index step giả: thêm ' [ENRICHED]' vào mỗi embed_text (không đụng chunk.text)."""

    name = "append"

    async def process(self, ctx: IndexContext) -> None:
        ctx.embed_texts = [t + " [ENRICHED]" for t in ctx.embed_texts]


def test_no_index_step_preserves_phase1_behavior():
    """Không index step: embed đúng chunk.text, store đúng chunk.text."""
    emb = FakeEmbedding()
    store = FakeIndexStore(exists=False)
    pipe = DocumentPipeline(emb, store)

    result = run(pipe.process_document(_TXT, "luat.txt", _meta()))

    assert result.soChunks == 2
    # embed nhận đúng text gốc của chunk
    assert emb.last_batch == [c.text for c in store.added_chunks]
    # store lưu chunk gốc
    assert all("[ENRICHED]" not in c.text for c in store.added_chunks)


def test_index_step_enriches_embed_but_stores_original():
    """Có index step: embed_texts bị sửa, nhưng chunk.text (store) giữ nguyên."""
    emb = FakeEmbedding()
    store = FakeIndexStore(exists=False)
    pipe = DocumentPipeline(emb, store, index_steps=[_AppendStep()])

    run(pipe.process_document(_TXT, "luat.txt", _meta()))

    # embed nhận text đã enrich
    assert all(t.endswith(" [ENRICHED]") for t in emb.last_batch)
    # nhưng store lưu chunk.text GỐC (không enrich) → hiển thị/trích dẫn sạch
    assert all("[ENRICHED]" not in c.text for c in store.added_chunks)
    # số lượng khớp
    assert len(emb.last_batch) == len(store.added_chunks)


def test_load_index_steps_skips_missing_module():
    """Index step bật nhưng không có file → bỏ qua, không crash."""
    deps = IndexDeps(settings=None, primary_llm=None, embedding=None)
    assert load_index_steps(["khong_ton_tai"], deps) == []
