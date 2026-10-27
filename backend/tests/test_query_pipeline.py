"""Test QueryPipeline — PHASE 1: gating, synthesis, độ tin cậy, fallback.

Không kiểm tra hybrid (query_text) ở đây → file chạy được trên cả phase-1 lẫn phase-2.
Test wiring query_text (Phase 2) nằm ở test_hybrid_search.py.
"""

from app.pipelines.query_pipeline import QueryPipeline
from tests.fakes import FakeEmbedding, FakeLLM, FakeStore, make_result, make_settings, run


def _pipeline(results, llm=None):
    return QueryPipeline(llm or FakeLLM(), FakeEmbedding(), FakeStore(results), make_settings())


# ----------------------- gating -----------------------

def test_no_results():
    res = run(_pipeline([]).process_query("câu hỏi bất kỳ"))
    assert res.doTinCay == "thấp"
    assert res.trichDan == []
    assert "Không tìm thấy điều khoản" in res.noiDung


def test_below_min_threshold():
    """max score < 0.3 → coi như không tìm thấy, KHÔNG gọi LLM."""
    llm = FakeLLM()
    res = run(_pipeline([make_result("Điều 8", 0.2)], llm).process_query("q"))
    assert res.doTinCay == "thấp"
    assert res.trichDan == []
    assert llm.called is False


def test_below_confident_threshold():
    """0.3 <= max < 0.5 → 'chưa đủ liên quan', KHÔNG gọi LLM."""
    llm = FakeLLM()
    res = run(_pipeline([make_result("Điều 8", 0.4)], llm).process_query("q"))
    assert res.doTinCay == "thấp"
    assert res.trichDan == []
    assert "đủ liên quan" in res.noiDung
    assert llm.called is False


# ----------------------- synthesis + confidence -----------------------

def test_synthesis_medium_confidence():
    llm = FakeLLM(content="**Câu trả lời** có trích dẫn [1].")
    res = run(_pipeline([make_result("Điều 8", 0.6), make_result("Điều 9", 0.55)], llm).process_query("q"))
    assert llm.called is True
    assert res.doTinCay == "trung bình"      # 0.5 <= 0.6 < 0.8
    assert res.noiDung == "**Câu trả lời** có trích dẫn [1]."
    assert len(res.trichDan) == 2
    assert res.trichDan[0].soHieu == "36/2024/QH15"


def test_synthesis_high_confidence():
    res = run(_pipeline([make_result("Điều 8", 0.9)]).process_query("q"))
    assert res.doTinCay == "cao"             # >= 0.8


# ----------------------- fallback -----------------------

def test_fallback_when_llm_fails():
    llm = FakeLLM(raise_exc=True)
    res = run(_pipeline([make_result("Điều 8", 0.7)], llm).process_query("q"))
    assert res.chunksGoc is not None
    assert len(res.chunksGoc) == 1
    assert "không khả dụng" in res.noiDung
    assert len(res.trichDan) == 1            # vẫn có trích dẫn
