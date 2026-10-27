"""Export chunk của 4 văn bản luật ra JSONL để enrich THỦ CÔNG (vd nhờ NotebookLM).

Chạy CHÍNH hàm chunk của dự án → seq khớp tuyệt đối với lúc seed_data.py nạp DB.
Mỗi dòng JSONL: {"soHieu", "seq", "dieu", "text_goc", "enrich": ""}.
Bạn điền trường "enrich" (tóm tắt + từ khóa + câu hỏi đời thường) rồi dùng:
    seed_data.py --reset   (với ENRICH_SOURCE=file, ENRICH_FILE=enrich_data.jsonl trong .env)

Chạy từ gốc dự án:
    backend\\.venv\\Scripts\\python.exe export_chunks_for_enrich.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / "backend"))

# Dùng CHUNG metadata seed với seed_data.py để soHieu/tên khớp.
from seed_data import SEED_DIR, SEED_META  # noqa: E402

from app.chunking.chunker import DocumentMetadata, VietnameseLawChunker  # noqa: E402
from app.pipelines.document_pipeline import DocumentPipeline  # noqa: E402

OUT_FILE = _ROOT / "enrich_data.jsonl"
PROMPT_FILE = _ROOT / "enrich_prompt_notebooklm.txt"

_PROMPT = """\
HƯỚNG DẪN DÙNG NOTEBOOKLM (hoặc ChatGPT/Gemini web) ĐỂ ĐIỀN TRƯỜNG "enrich"

Mục tiêu: với MỖI dòng trong enrich_data.jsonl, sinh phần BỔ SUNG TÌM KIẾM cho đoạn
luật ở trường "text_goc", rồi dán vào trường "enrich" của ĐÚNG dòng đó.

Phần "enrich" cần gồm, bằng tiếng Việt, ngắn gọn:
- TÓM TẮT: 1-2 câu nội dung chính của đoạn.
- TỪ KHÓA: đối tượng/loại xe, con số, mức phạt, chủ đề — KÈM cách gọi dân dã.
- CÂU HỎI: 3-5 câu hỏi đời thường mà đoạn này trả lời (đa dạng cách diễn đạt).

BẮT BUỘC thêm CÁCH GỌI DÂN DÃ cho thuật ngữ pháp lý, ví dụ:
- "không chấp hành hiệu lệnh của đèn tín hiệu" -> "vượt đèn đỏ, vượt đèn vàng"
- "nồng độ cồn" -> "uống rượu bia lái xe, say xỉn"
- "vượt quá tốc độ quy định" -> "chạy quá tốc độ, chạy nhanh"
- "đi ngược chiều của đường một chiều" -> "chạy ngược chiều"

QUY TẮC:
- CHỈ dựa trên "text_goc", KHÔNG bịa thêm điều luật/mức phạt.
- Nếu đoạn liệt kê nhiều hành vi (điểm a, b, c...), tạo từ khóa + câu hỏi cho TỪNG hành vi.
- KHÔNG đổi "soHieu", "seq", "text_goc" — chỉ điền "enrich".
"""


def main() -> None:
    chunker = VietnameseLawChunker()
    pipeline = DocumentPipeline.__new__(DocumentPipeline)  # chỉ cần _parse, không khởi tạo deps
    rows: list[dict] = []
    total = 0

    for filename, meta in SEED_META.items():
        path = SEED_DIR / filename
        if not path.is_file():
            print(f"[THIEU] {filename}")
            continue
        ext = filename.rsplit(".", 1)[-1].lower()
        raw_text = DocumentPipeline._parse(pipeline, path.read_bytes(), ext)
        base_meta = DocumentMetadata(
            soHieu=meta["soHieu"], tenVanBan=meta["tenVanBan"],
            ngayBanHanh=meta["ngayBanHanh"], ngayHieuLuc=meta["ngayHieuLuc"],
            coQuanBanHanh=meta.get("coQuanBanHanh", ""), loaiVanBan=meta.get("loaiVanBan", ""),
        )
        chunks = chunker.chunk_document(raw_text, base_meta)
        for seq, c in enumerate(chunks):
            rows.append({
                "soHieu": c.metadata.soHieu,
                "seq": seq,
                "dieu": c.metadata.dieu or "",
                "text_goc": c.text,
                "enrich": "",
            })
        print(f"[OK] {meta['soHieu']}: {len(chunks)} chunk")
        total += len(chunks)

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    PROMPT_FILE.write_text(_PROMPT, encoding="utf-8")

    print("-" * 60)
    print(f"Da ghi {total} chunk -> {OUT_FILE}")
    print(f"Huong dan NotebookLM -> {PROMPT_FILE}")
    print("Dien truong 'enrich' cho tung dong, roi chay seed_data.py --reset "
          "(voi ENRICH_SOURCE=file trong .env).")


if __name__ == "__main__":
    main()
