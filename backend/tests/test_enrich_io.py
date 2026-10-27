"""Test export/import enrich dạng text (Phase 4). Chỉ trên nhánh có Phase 4."""

import json
from pathlib import Path

import pytest

from app.indexing.enrich_io import (
    apply_enrich_to_jsonl,
    build_export_text,
    parse_import_text,
)


def _write_jsonl(tmp_path, rows) -> Path:
    p = tmp_path / "enrich.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def _rows():
    return [
        {"soHieu": "A/2024", "seq": 0, "text_goc": "Điều 1 A.", "enrich": ""},
        {"soHieu": "A/2024", "seq": 1, "text_goc": "Điều 2 A.", "enrich": ""},
        {"soHieu": "B/2024", "seq": 0, "text_goc": "Điều 1 B.", "enrich": "GIU-NGUYEN-B"},
    ]


def test_export_only_selected_document(tmp_path):
    p = _write_jsonl(tmp_path, _rows())
    content, n = build_export_text(p, "A/2024")
    assert n == 2
    assert "soHieu=A/2024" in content
    assert "soHieu=B/2024" not in content          # không lẫn văn bản khác
    assert "Điều 1 A." in content and "Điều 2 A." in content
    assert "HƯỚNG DẪN CHO TOOL" in content          # có prompt


def test_export_unknown_document_raises(tmp_path):
    p = _write_jsonl(tmp_path, _rows())
    with pytest.raises(ValueError):
        build_export_text(p, "KHONG-CO")


def test_parse_import_text_extracts_soHieu_and_enrich():
    text = (
        "### CHUNK seq=0 soHieu=A/2024 ###\n"
        "TEXT_GOC:\nĐiều 1 A.\nENRICH:\nTÓM TẮT: abc\n### END ###\n"
        "### CHUNK seq=1 soHieu=A/2024 ###\n"
        "TEXT_GOC:\nĐiều 2 A.\nENRICH:\nTÓM TẮT: def\n### END ###\n"
    )
    so_hieu, by_seq = parse_import_text(text)
    assert so_hieu == "A/2024"
    assert by_seq[0].startswith("TÓM TẮT: abc")
    assert by_seq[1].startswith("TÓM TẮT: def")


def test_parse_import_rejects_multiple_documents():
    text = (
        "### CHUNK seq=0 soHieu=A/2024 ###\nENRICH:\nx\n### END ###\n"
        "### CHUNK seq=0 soHieu=B/2024 ###\nENRICH:\ny\n### END ###\n"
    )
    with pytest.raises(ValueError):
        parse_import_text(text)


def test_parse_import_rejects_garbage():
    with pytest.raises(ValueError):
        parse_import_text("khong co marker gi ca")


def test_apply_updates_only_target_document(tmp_path):
    p = _write_jsonl(tmp_path, _rows())
    stats = apply_enrich_to_jsonl(p, "A/2024", {0: "E0", 1: "E1"})
    assert stats["filled"] == 2 and stats["total_doc_rows"] == 2

    rows = [json.loads(l) for l in p.open(encoding="utf-8")]
    by = {(r["soHieu"], r["seq"]): r["enrich"] for r in rows}
    assert by[("A/2024", 0)] == "E0"
    assert by[("A/2024", 1)] == "E1"
    assert by[("B/2024", 0)] == "GIU-NGUYEN-B"   # văn bản khác GIỮ NGUYÊN


def test_apply_unknown_document_raises(tmp_path):
    p = _write_jsonl(tmp_path, _rows())
    with pytest.raises(ValueError):
        apply_enrich_to_jsonl(p, "KHONG-CO", {0: "x"})


def test_export_import_roundtrip(tmp_path):
    """Export -> điền ENRICH -> parse -> apply: khớp đúng seq."""
    p = _write_jsonl(tmp_path, _rows())
    content, _ = build_export_text(p, "A/2024")
    # Giả lập tool điền: thay 'ENRICH:\n' trống bằng nội dung.
    filled = content.replace("ENRICH:\n\n", "ENRICH:\nNOI-DUNG\n")
    so_hieu, by_seq = parse_import_text(filled)
    stats = apply_enrich_to_jsonl(p, so_hieu, by_seq)
    assert so_hieu == "A/2024"
    assert stats["filled"] == 2
