"""Kiem tra enrich_data.jsonl TRUOC khi seed (khong ghi DB).

So khop voi chunk THAT ma pipeline se tao: dung soHieu, dung seq, text_goc khop.
Bao: tong dong, so dong co enrich, dong lech/thieu/thua.

Chay tu goc du an:
    backend\\.venv\\Scripts\\python.exe check_enrich_file.py
    backend\\.venv\\Scripts\\python.exe check_enrich_file.py duong_dan_khac.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "backend"))

from seed_data import SEED_DIR, SEED_META  # noqa: E402

from app.chunking.chunker import DocumentMetadata, VietnameseLawChunker  # noqa: E402
from app.pipelines.document_pipeline import DocumentPipeline  # noqa: E402


def _norm(s: str) -> str:
    return " ".join((s or "").split())[:120]


def main() -> None:
    jsonl_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _ROOT / "enrich_data.jsonl"
    if not jsonl_path.is_file():
        print(f"[LOI] Khong thay file: {jsonl_path}")
        sys.exit(1)

    # 1. Doc JSONL -> map (soHieu, seq) -> row
    rows: dict[tuple[str, int], dict] = {}
    bad_lines = 0
    have_enrich = 0
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"[JSON LOI] dong {line_no}: {exc}")
                bad_lines += 1
                continue
            key = (str(r.get("soHieu", "")), int(r.get("seq", -1)))
            rows[key] = r
            if (r.get("enrich") or "").strip():
                have_enrich += 1

    print(f"File: {jsonl_path}")
    print(f"Tong dong JSONL hop le: {len(rows)} | co enrich: {have_enrich} | dong hong: {bad_lines}")
    print("-" * 60)

    # 2. Dung chunk THAT tu PDF de doi chieu
    chunker = VietnameseLawChunker()
    pipe = DocumentPipeline.__new__(DocumentPipeline)
    total_chunks = 0
    missing = 0      # chunk that nhung JSONL khong co dong
    mismatch = 0     # co dong nhung text_goc lech
    seen_keys: set[tuple[str, int]] = set()

    for filename, meta in SEED_META.items():
        path = SEED_DIR / filename
        if not path.is_file():
            print(f"[THIEU PDF] {filename}")
            continue
        ext = filename.rsplit(".", 1)[-1].lower()
        raw = DocumentPipeline._parse(pipe, path.read_bytes(), ext)
        base = DocumentMetadata(
            soHieu=meta["soHieu"], tenVanBan=meta["tenVanBan"],
            ngayBanHanh=meta["ngayBanHanh"], ngayHieuLuc=meta["ngayHieuLuc"],
            coQuanBanHanh=meta.get("coQuanBanHanh", ""), loaiVanBan=meta.get("loaiVanBan", ""),
        )
        chunks = chunker.chunk_document(raw, base)
        file_missing = file_mismatch = 0
        for seq, c in enumerate(chunks):
            total_chunks += 1
            key = (c.metadata.soHieu, seq)
            seen_keys.add(key)
            row = rows.get(key)
            if row is None:
                missing += 1
                file_missing += 1
                continue
            if row.get("text_goc") and _norm(row["text_goc"]) != _norm(c.text):
                mismatch += 1
                file_mismatch += 1
        print(f"  {meta['soHieu']}: {len(chunks)} chunk | thieu dong={file_missing} | text lech={file_mismatch}")

    extra = [k for k in rows if k not in seen_keys]

    print("-" * 60)
    print(f"Tong chunk that: {total_chunks}")
    print(f"Dong JSONL THIEU (chunk khong co enrich -> giu goc): {missing}")
    print(f"Dong text_goc LECH (co the gan nham): {mismatch}")
    print(f"Dong JSONL THUA (khong khop chunk nao): {len(extra)}")
    if extra[:5]:
        print("  Vi du thua:", extra[:5])

    print("=" * 60)
    if bad_lines == 0 and mismatch == 0 and len(extra) == 0:
        print("[OK] File hop le. Co the chay: seed_data.py --reset")
        if missing:
            print(f"     Luu y: {missing} chunk chua co enrich -> se giu text goc (van chay duoc).")
    else:
        print("[CANH BAO] Co van de o tren. Nen sua truoc khi seed.")


if __name__ == "__main__":
    main()
