# RAG Tra cứu Luật Giao Thông Việt Nam

Hệ thống **RAG (Retrieval-Augmented Generation)** cho phép người dùng mô tả tình huống giao
thông bằng tiếng Việt → hệ thống tìm đúng điều luật liên quan → LLM tổng hợp câu trả lời có
**trích dẫn nguồn** (số hiệu, Điều, Khoản) kèm **nhãn độ tin cậy**. Giao diện chat.

Nguyên tắc cốt lõi: **chỉ trả lời dựa trên văn bản luật thật, không bịa** (chống hallucination).
Thêm luật mới = upload file, **không cần huấn luyện lại**.

Bản này gồm: **Phase 1** (core RAG + chat UI) + **Phase 2** (hybrid search BM25+RRF) +
**Phase 4** (enrich chunk tăng recall câu hỏi đời thường).

---

## Kiến trúc

```
[Frontend React]  --HTTP/JSON-->  [FastAPI backend]
                                     |
   Indexing: parse -> chunk -> (enrich) -> embed -> ChromaDB
   Query:    embed -> hybrid search (vector + BM25 + RRF) -> gating -> LLM synthesis -> trả lời
```

| Tầng | Công nghệ |
|---|---|
| Frontend | React 19 + Vite + TypeScript + Tailwind |
| Backend | Python 3.11+ / FastAPI (async) |
| Vector DB | ChromaDB (embedded, cosine) |
| Embedding | sentence-transformers `intfloat/multilingual-e5-large` (1024 chiều, chạy CPU) |
| LLM synthesis | Cấu hình qua `.env` (Groq / Mistral / Cohere / Ollama / Gemini) |
| Parse PDF | PyMuPDF |

---

## Yêu cầu

- Python 3.11+ (khuyến nghị), Node.js 18+ / npm
- (Tùy chọn) Ollama nếu muốn chạy LLM local

---

## Cài đặt & Chạy (Windows / PowerShell)

```powershell
# 1. Setup 1 lần (tạo venv + cài deps backend, npm install frontend, tạo .env)
.\setup.bat

# 2. Điền API key vào backend/.env (copy từ backend/.env.example)
#    Tối thiểu: provider LLM synthesis bạn chọn (PRIMARY_LLM_PROVIDER + key tương ứng).

# 3. Nạp dữ liệu (xem phần Dữ liệu bên dưới) — hoặc dùng DB có sẵn trong "Sample Data/"

# 4. Chạy cả backend (8000) + frontend (5173)
.\run_all.bat
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

> Dùng `python -m uvicorn` / `python -m pip` nếu gọi .exe bị chặn.

---

## Dữ liệu

Thư mục **`Sample Data/`** chứa dữ liệu mẫu để chạy ngay. Xem `Sample Data/README.md`.
Tóm tắt 3 cách:

```powershell
# A. Dùng Vector DB đã build sẵn (nhanh nhất)
Copy-Item -Recurse -Force "Sample Data\data\chroma\*" "data\chroma\"

# B. Build lại từ seed + enrich có sẵn (không cần API)
Copy-Item "Sample Data\enrich_data.jsonl" "enrich_data.jsonl" -Force
backend\.venv\Scripts\python.exe seed_data.py --reset --enrich file

# C. Seed không enrich
backend\.venv\Scripts\python.exe seed_data.py --reset --enrich none
```

---

## Enrich (làm giàu chunk, tăng recall câu hỏi đời thường)

Enrich sinh "tóm tắt + từ khóa dân dã + câu hỏi đời thường" gắn vào text-để-embed
(chunk gốc giữ nguyên để trích dẫn). Ví dụ: "không chấp hành hiệu lệnh đèn tín hiệu"
→ gắn thêm "vượt đèn đỏ".

Chọn chế độ enrich **khi nạp** (không cấu hình ở `.env`):

- **Qua Admin UI** (form "Tải lên văn bản mới"): radio **Không / Tự động (LLM) / Thủ công (file)**.
  Thủ công: nút **Get chunk** → điền bằng NotebookLM/ChatGPT theo prompt trong file →
  chọn file đã điền → Tải lên.
- **Qua CLI**: `seed_data.py --enrich none|auto|file`
  (`file` đọc `ENRICH_FILE`; `auto` dùng `ENRICH_LLM_*` trong `.env`).

Công cụ hỗ trợ ở gốc dự án: `export_chunks_for_enrich.py` (xuất chunk), `check_enrich_file.py`
(kiểm tra file enrich trước khi seed).

---

## Kiểm thử

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # 1 lần
.\.venv\Scripts\python.exe -m pytest
```

Test dùng fake Embedding/LLM + ChromaDB in-memory → nhanh, không cần model 2GB hay gọi API.

---

## Cấu trúc thư mục (rút gọn)

```
backend/app/
  api/            # routes (query, documents, auth) + DI
  chunking/       # VietnameseLawChunker (cắt theo Điều)
  indexing/       # index step: enrich (enrich_step, enrich_io)
  pipelines/      # document_pipeline, query_pipeline
  prompts/        # system prompts
  providers/      # LLM + embedding providers
  retrieval/      # vector / hybrid strategy (BM25 + RRF)
  storage/        # ChromaDB wrapper
frontend/src/     # React chat UI + trang Admin
data/seed/        # 4 PDF luật gốc
Sample Data/      # DB build sẵn + enrich_data.jsonl + README
docs/             # tài liệu thiết kế
```

---

## Lưu ý bảo mật

- **Không commit `backend/.env`** (chứa API key). Chỉ dùng `backend/.env.example` làm mẫu.
- Vector DB build bằng `multilingual-e5-large` — truy vấn phải dùng đúng model này.
