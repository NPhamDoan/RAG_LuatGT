"""Test export enrich dạng text + parse import lọc theo số hiệu."""

import json
from pathlib import Path

import pytest

from app.indexing.enrich_io import build_export_text, parse_import_filtered


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


def test_parse_import_filtered_keeps_only_target_document():
    text = (
        "### CHUNK seq=0 soHieu=A/2024 ###\nENRICH:\nx0\n### END ###\n"
        "### CHUNK seq=1 soHieu=A/2024 ###\nENRICH:\nx1\n### END ###\n"
        "### CHUNK seq=0 soHieu=B/2024 ###\nENRICH:\ny\n### END ###\n"
    )
    enrich_by_seq, skipped = parse_import_filtered(text, "A/2024")
    assert enrich_by_seq == {0: "x0", 1: "x1"}
    assert skipped == 1                              # khối B/2024 bị bỏ qua


def test_parse_import_filtered_no_matching_document_raises():
    text = "### CHUNK seq=0 soHieu=B/2024 ###\nENRICH:\ny\n### END ###\n"
    with pytest.raises(ValueError):
        parse_import_filtered(text, "A/2024")


def test_parse_import_filtered_rejects_garbage():
    with pytest.raises(ValueError):
        parse_import_filtered("khong co marker gi ca", "A/2024")
