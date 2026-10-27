"""Export/Import enrich theo định dạng TEXT (cho tool ngoài như NotebookLM).

Vì tool web thường không cho tải .json, ta dùng .txt dạng KHỐI có marker rõ ràng:
mỗi chunk một khối, tool chỉ điền phần dưới "ENRICH:", giữ nguyên marker.

Nguồn dữ liệu gốc là ENRICH_FILE (jsonl) hiện có — đã chứa soHieu/seq/text_goc cho
mọi chunk. Export = lọc theo soHieu, dựng khối text. Import = parse khối, ghép enrich
theo (soHieu, seq) vào lại jsonl chung (CHỈ cập nhật phần văn bản đó).
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Gốc repo (backend/..). ENRICH_FILE tương đối tính theo đây — khớp enrich_step.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def get_enrich_file_path() -> Path:
    """Đường dẫn ENRICH_FILE (đọc .env, như enrich_step). Mặc định enrich_data.jsonl."""
    value = ""
    # Ưu tiên env var (test/CI), rồi tới dòng ENRICH_FILE trong backend/.env.
    value = os.environ.get("ENRICH_FILE", "")
    if not value and _ENV_FILE.is_file():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("ENRICH_FILE") and "=" in line:
                value = line.split("=", 1)[1].strip()
                break
    value = value or "enrich_data.jsonl"
    p = Path(value)
    return p if p.is_absolute() else _REPO_ROOT / p

_CHUNK_RE = re.compile(
    r"###\s*CHUNK\s+seq=(\d+)\s+soHieu=(.+?)\s*###(.*?)###\s*END\s*###",
    re.DOTALL,
)
_ENRICH_RE = re.compile(r"ENRICH:\s*(.*)", re.DOTALL)

_PROMPT_HEADER = """\
=== HƯỚNG DẪN CHO TOOL (NotebookLM/ChatGPT/Gemini) — ĐỌC KỸ ===

Nhiệm vụ: với MỖI khối "### CHUNK ... ###" bên dưới, điền phần làm giàu tìm kiếm
vào NGAY DƯỚI dòng "ENRICH:" của chính khối đó.

QUY TẮC XUẤT (bắt buộc để hệ thống đọc lại được):
- GIỮ NGUYÊN mọi dòng marker: "### CHUNK seq=N soHieu=... ###" và "### END ###".
  KHÔNG sửa, KHÔNG xóa, KHÔNG đổi số seq/soHieu.
- KHÔNG bọc kết quả trong ``` hay thẻ code. Trả về TEXT THUẦN.
- Chỉ VIẾT THÊM nội dung dưới "ENRICH:", KHÔNG đụng phần "TEXT_GOC:".
- Giữ đúng thứ tự các khối.

NỘI DUNG ENRICH cho mỗi khối (tiếng Việt, ngắn gọn), gồm:
  TÓM TẮT: 1-2 câu nội dung chính.
  TỪ KHÓA: đối tượng/loại xe, con số, mức phạt, chủ đề — KÈM cách gọi dân dã
           (vd "không chấp hành hiệu lệnh đèn tín hiệu" -> "vượt đèn đỏ";
            "nồng độ cồn" -> "uống rượu bia, say xỉn";
            "quá tốc độ" -> "chạy nhanh").
  CÂU HỎI: 3-5 câu hỏi đời thường mà đoạn này trả lời.
- CHỈ dựa trên TEXT_GOC, KHÔNG bịa điều luật/mức phạt.
- Nếu đoạn liệt kê nhiều hành vi (a, b, c...), làm từ khóa + câu hỏi cho TỪNG hành vi.

VÍ DỤ phần ENRICH đã điền đúng (chỉ minh họa — KHÔNG phải khối thật):
  TÓM TẮT: Quy định mức phạt với hành vi ...
  TỪ KHÓA: ô tô, vượt đèn đỏ, không chấp hành đèn tín hiệu
  CÂU HỎI:
  - Vượt đèn đỏ ô tô phạt bao nhiêu?
  - Không chấp hành đèn tín hiệu bị xử lý thế nào?

=== BẮT ĐẦU DỮ LIỆU (điền vào, rồi lưu lại thành .txt và tải lên hệ thống) ===

"""


def _blocks_to_text(blocks: list[str]) -> str:
    return _PROMPT_HEADER + "\n\n".join(blocks) + "\n"


def build_export_text(jsonl_path: Path, so_hieu: str) -> tuple[str, int]:
    """Export cho văn bản ĐÃ NẠP — đọc chunk từ file enrich jsonl hiện có."""
    rows = _read_jsonl(jsonl_path)
    blocks: list[str] = []
    for r in rows:
        if str(r.get("soHieu", "")) != so_hieu:
            continue
        blocks.append(_make_block(r.get("seq"), so_hieu, r.get("text_goc", ""),
                                  (r.get("enrich") or "").strip()))
    if not blocks:
        raise ValueError(f"Không có chunk nào cho soHieu={so_hieu} trong {jsonl_path.name}")
    return _blocks_to_text(blocks), len(blocks)


def build_export_from_chunks(chunks: list, so_hieu: str) -> tuple[str, int]:
    """Export cho văn bản CHƯA NẠP — chunk vừa tạo từ PDF đang upload (form Admin 'Get chunk').

    chunks: list[Chunk] đã chunk; seq = thứ tự trong list → KHỚP lúc nạp (cùng hàm chunk).
    """
    blocks = [
        _make_block(seq, so_hieu, c.text, "")
        for seq, c in enumerate(chunks)
    ]
    if not blocks:
        raise ValueError("Không có chunk nào từ văn bản.")
    return _blocks_to_text(blocks), len(blocks)


def _make_block(seq, so_hieu: str, text_goc: str, enrich: str) -> str:
    return (
        f"### CHUNK seq={seq} soHieu={so_hieu} ###\n"
        f"TEXT_GOC:\n{text_goc}\n"
        f"ENRICH:\n{enrich}\n"
        f"### END ###"
    )


def parse_import_text(text: str) -> tuple[str, dict[int, str]]:
    """Parse text tool trả về → (soHieu, {seq: enrich}).

    Lỗi nếu file chứa nhiều soHieu khác nhau (mỗi lần import 1 văn bản).
    """
    matches = _CHUNK_RE.findall(text)
    if not matches:
        raise ValueError("Không tìm thấy khối '### CHUNK ... ###' nào — sai định dạng file.")

    so_hieu_set: set[str] = set()
    enrich_by_seq: dict[int, str] = {}
    for seq_str, so_hieu, body in matches:
        so_hieu = so_hieu.strip()
        so_hieu_set.add(so_hieu)
        m = _ENRICH_RE.search(body)
        enrich = m.group(1).strip() if m else ""
        enrich_by_seq[int(seq_str)] = enrich

    if len(so_hieu_set) != 1:
        raise ValueError(
            f"File chứa nhiều số hiệu khác nhau: {sorted(so_hieu_set)}. "
            "Mỗi lần chỉ import một văn bản."
        )
    return so_hieu_set.pop(), enrich_by_seq


def parse_import_filtered(text: str, expected_so_hieu: str) -> tuple[dict[int, str], int]:
    """Parse text, CHỈ lấy khối có soHieu == expected (cách lỏng).

    Khối soHieu khác → bỏ qua, đếm vào 'skipped'. Trả ({seq: enrich}, skipped).
    Lỗi nếu KHÔNG có khối nào thuộc expected_so_hieu.
    """
    matches = _CHUNK_RE.findall(text)
    if not matches:
        raise ValueError("Không tìm thấy khối '### CHUNK ... ###' nào — sai định dạng file.")

    enrich_by_seq: dict[int, str] = {}
    skipped = 0
    for seq_str, so_hieu, body in matches:
        if so_hieu.strip() != expected_so_hieu:
            skipped += 1
            continue
        m = _ENRICH_RE.search(body)
        enrich_by_seq[int(seq_str)] = m.group(1).strip() if m else ""

    if not enrich_by_seq:
        raise ValueError(
            f"File không chứa khối nào thuộc số hiệu '{expected_so_hieu}'. "
            "Kiểm tra lại số hiệu ở metadata và nội dung file."
        )
    return enrich_by_seq, skipped


def apply_enrich_to_jsonl(
    jsonl_path: Path, so_hieu: str, enrich_by_seq: dict[int, str]
) -> dict:
    """Ghép enrich vào jsonl chung — CHỈ cập nhật dòng của so_hieu, giữ nguyên văn bản khác.

    Trả thống kê: {matched, filled, missing_seq, total_doc_rows}.
    """
    rows = _read_jsonl(jsonl_path)
    doc_seqs = {int(r["seq"]) for r in rows if str(r.get("soHieu", "")) == so_hieu}
    if not doc_seqs:
        raise ValueError(f"Số hiệu '{so_hieu}' không có trong hệ thống — không thể import.")

    filled = 0
    matched = 0
    for r in rows:
        if str(r.get("soHieu", "")) != so_hieu:
            continue
        seq = int(r["seq"])
        if seq in enrich_by_seq:
            matched += 1
            val = enrich_by_seq[seq].strip()
            if val:
                r["enrich"] = val
                filled += 1

    _write_jsonl(jsonl_path, rows)
    # seq trong file import nhưng không có chunk tương ứng → cảnh báo thừa.
    extra_seqs = sorted(set(enrich_by_seq) - doc_seqs)
    return {
        "soHieu": so_hieu,
        "total_doc_rows": len(doc_seqs),
        "matched": matched,
        "filled": filled,
        "extra_seqs": extra_seqs[:10],
    }


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Không thấy file enrich: {path}")
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
