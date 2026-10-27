# Sample Data — RAG Luật Giao Thông

Thư mục này chứa **dữ liệu mẫu** để chạy hệ thống ngay, hoặc dựng lại Vector DB từ đầu.

## Nội dung

| Mục | Mô tả |
|---|---|
| `data/seed/*.pdf` | 4 văn bản luật gốc (Luật 36, 35; Thông tư 38; Nghị định 168/2024) |
| `data/chroma/` | **Vector DB (ChromaDB) đã build sẵn** — 597 chunk, đã enrich. Dùng được ngay. |
| `enrich_data.jsonl` | Dữ liệu enrich (597 dòng: tóm tắt + từ khóa + câu hỏi đời thường cho mỗi chunk) |

## Cách 1 — Dùng Vector DB có sẵn (nhanh nhất)

Copy thư mục `data/chroma/` vào vị trí ChromaDB mà backend đọc (mặc định `./data/chroma`
tính từ gốc dự án), rồi chạy backend. Không cần seed lại.

```powershell
# Từ gốc dự án
Copy-Item -Recurse -Force "Sample Data\data\chroma\*" "data\chroma\"
```

> Lưu ý: Vector DB này được build bằng embedding `intfloat/multilingual-e5-large` (1024 chiều).
> Phải dùng đúng model đó (mặc định trong `.env`) thì vector mới tương thích khi truy vấn.

## Cách 2 — Dựng lại DB từ seed + enrich (tái lập đầy đủ)

Nếu muốn build lại từ đầu với chính dữ liệu enrich kèm theo:

```powershell
# 1. Đặt file enrich đúng chỗ backend đọc (ENRICH_FILE trong backend/.env, mặc định enrich_data.jsonl ở gốc)
Copy-Item "Sample Data\enrich_data.jsonl" "enrich_data.jsonl" -Force

# 2. Bảo đảm 4 PDF có trong data/seed/ (đã có sẵn trong repo)

# 3. Seed lại, enrich lấy từ file (không cần API/LLM)
backend\.venv\Scripts\python.exe seed_data.py --reset --enrich file
```

Kết quả: Vector DB mới giống hệt bản build sẵn ở Cách 1.

## Cách 3 — Seed không enrich (tối giản)

```powershell
backend\.venv\Scripts\python.exe seed_data.py --reset --enrich none
```

## Enrich lại / cho văn bản mới

- Qua Admin UI: form "Tải lên văn bản mới" → chọn **Thủ công (file)** → **Get chunk** → điền bằng
  NotebookLM/ChatGPT theo prompt trong file → **chọn file** đã điền → **Tải lên**.
- Hoặc dùng `export_chunks_for_enrich.py` (xuất) và `check_enrich_file.py` (kiểm tra) ở gốc dự án.
