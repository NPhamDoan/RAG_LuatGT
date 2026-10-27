"""Test PHASE 4: Enrich step (index-time làm giàu chunk).

Phụ thuộc code Phase 4 (app/indexing/enrich_step.py) → CHỈ trên nhánh có Phase 4.
"""

from datetime import date

from app.indexing.base import IndexContext, IndexDeps
from app.indexing.enrich_step import EnrichStep, build
from app.models.schemas import DocumentMetadataInput
from app.pipelines.document_pipeline import DocumentPipeline
from tests.fakes import FakeEmbedding, FakeIndexStore, FakeLLM, make_chunk, run


def _ctx(chunks):
    return IndexContext(chunks=chunks, embed_texts=[c.text for c in chunks])


def test_enrich_appends_to_embed_text_only():
    """embed_text = text gốc + enrichment; chunk.text gốc KHÔNG đổi."""
    llm = FakeLLM(content="Chạy quá tốc độ phạt bao nhiêu?\nKhu dân cư tối đa mấy km/h?")
    step = EnrichStep(llm)
    chunks = [make_chunk("VB1", "Điều 8", "Tốc độ tối đa trong khu dân cư là 60 km/h.")]
    ctx = _ctx(chunks)

    run(step.process(ctx))

    assert ctx.embed_texts[0].startswith(chunks[0].text)      # bắt đầu bằng text gốc
    assert "Chạy quá tốc độ" in ctx.embed_texts[0]            # có enrichment
    assert "[Bổ sung tìm kiếm]" in ctx.embed_texts[0]
    assert chunks[0].text == "Tốc độ tối đa trong khu dân cư là 60 km/h."  # gốc nguyên vẹn


def test_enrich_llm_failure_keeps_original():
    """LLM lỗi cho chunk → embed_text giữ nguyên text gốc, không crash."""
    step = EnrichStep(FakeLLM(raise_exc=True))
    chunks = [make_chunk("VB1", "Điều 8", "Nội dung điều 8.")]
    ctx = _ctx(chunks)

    run(step.process(ctx))

    assert ctx.embed_texts[0] == chunks[0].text


def test_enrich_empty_chunks():
    step = EnrichStep(FakeLLM())
    ctx = IndexContext(chunks=[], embed_texts=[])
    run(step.process(ctx))
    assert ctx.embed_texts == []


def test_build_returns_enrich_step(monkeypatch):
    """Không set ENRICH_LLM_PROVIDER → dùng LLM synthesis chính (primary_llm)."""
    monkeypatch.setenv("ENRICH_SOURCE", "llm")      # độc lập ENRICH_SOURCE trong .env máy dev
    monkeypatch.setenv("ENRICH_LLM_PROVIDER", "")  # ép rỗng, độc lập .env máy dev
    fake = FakeLLM()
    step = build(IndexDeps(settings=None, primary_llm=fake, embedding=None))
    assert step.name == "enrich"
    assert step._llm is fake  # dùng đúng primary_llm


def test_build_uses_dedicated_llm_from_env(monkeypatch):
    """Set ENRICH_LLM_PROVIDER=groq → build tạo LLM riêng, KHÔNG dùng primary_llm."""
    monkeypatch.setenv("ENRICH_SOURCE", "llm")
    monkeypatch.setenv("ENRICH_LLM_PROVIDER", "groq")
    monkeypatch.setenv("ENRICH_LLM_MODEL", "test-model")
    monkeypatch.setenv("ENRICH_LLM_API_KEY", "dummy-key")

    fake = FakeLLM()
    step = build(IndexDeps(settings=None, primary_llm=fake, embedding=None))

    assert step.name == "enrich"
    assert step._llm is not fake
    assert type(step._llm).__name__ == "GroqProvider"


def test_build_unknown_provider_falls_back(monkeypatch):
    """Provider lạ → fallback về primary_llm (không crash)."""
    monkeypatch.setenv("ENRICH_SOURCE", "llm")
    monkeypatch.setenv("ENRICH_LLM_PROVIDER", "khong-ton-tai")
    fake = FakeLLM()
    step = build(IndexDeps(settings=None, primary_llm=fake, embedding=None))
    assert step._llm is fake


def test_enrich_through_document_pipeline():
    """Qua document_pipeline: embed nhận text enriched, store lưu chunk gốc."""
    llm = FakeLLM(content="Câu hỏi đời thường?")
    emb = FakeEmbedding()
    store = FakeIndexStore(exists=False)
    pipe = DocumentPipeline(emb, store, index_steps=[EnrichStep(llm)])

    txt = "Điều 1. Phạm vi điều chỉnh\nLuật này quy định chung.\n".encode("utf-8")
    meta = DocumentMetadataInput(
        soHieu="X/2024", tenVanBan="Test", ngayBanHanh=date(2024, 1, 1), ngayHieuLuc=date(2024, 1, 1)
    )
    run(pipe.process_document(txt, "a.txt", meta))

    assert any("Câu hỏi đời thường?" in t for t in emb.last_batch)          # embed enriched
    assert all("Câu hỏi đời thường?" not in c.text for c in store.added_chunks)  # store gốc


# ===== Nguồn FILE (enrich thủ công, vd NotebookLM) =====

def _write_jsonl(tmp_path, rows):
    import json
    p = tmp_path / "enrich.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def test_enrich_file_source_appends_from_file(tmp_path, monkeypatch):
    """ENRICH_SOURCE=file: ghép enrich từ JSONL theo (soHieu, seq); chunk.text gốc giữ nguyên."""
    chunks = [
        make_chunk("VB1", "Điều 1", "Nội dung điều một."),
        make_chunk("VB1", "Điều 2", "Nội dung điều hai."),
    ]
    jsonl = _write_jsonl(tmp_path, [
        {"soHieu": "VB1", "seq": 0, "text_goc": "Nội dung điều một.", "enrich": "ENRICH-MOT"},
        {"soHieu": "VB1", "seq": 1, "text_goc": "Nội dung điều hai.", "enrich": "ENRICH-HAI"},
    ])
    monkeypatch.setenv("ENRICH_SOURCE", "file")
    monkeypatch.setenv("ENRICH_FILE", str(jsonl))

    step = build(IndexDeps(settings=None, primary_llm=FakeLLM(), embedding=None))
    ctx = _ctx(chunks)
    run(step.process(ctx))

    assert "ENRICH-MOT" in ctx.embed_texts[0] and ctx.embed_texts[0].startswith(chunks[0].text)
    assert "ENRICH-HAI" in ctx.embed_texts[1]
    assert "[Bổ sung tìm kiếm]" in ctx.embed_texts[0]
    assert chunks[0].text == "Nội dung điều một."  # gốc nguyên vẹn
    assert step.manifest_info()["enrich_source"] == "file"


def test_enrich_file_missing_row_keeps_original(tmp_path, monkeypatch):
    """Dòng thiếu cho một chunk → chunk đó giữ text gốc (không crash)."""
    chunks = [
        make_chunk("VB1", "Điều 1", "Nội dung điều một."),
        make_chunk("VB1", "Điều 2", "Nội dung điều hai."),
    ]
    jsonl = _write_jsonl(tmp_path, [
        {"soHieu": "VB1", "seq": 0, "text_goc": "Nội dung điều một.", "enrich": "CHI-MOT"},
    ])
    monkeypatch.setenv("ENRICH_SOURCE", "file")
    monkeypatch.setenv("ENRICH_FILE", str(jsonl))

    step = build(IndexDeps(settings=None, primary_llm=FakeLLM(), embedding=None))
    ctx = _ctx(chunks)
    run(step.process(ctx))

    assert "CHI-MOT" in ctx.embed_texts[0]
    assert ctx.embed_texts[1] == chunks[1].text  # không có dòng → giữ gốc
