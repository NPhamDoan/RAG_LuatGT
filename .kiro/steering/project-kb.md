# PROJECT KB — RAG Tra cứu Luật Giao Thông Việt Nam

> Tài liệu ngữ cảnh dự án (knowledge base). Đọc file này là đủ hiểu dự án làm gì, kiến trúc,
> trạng thái từng phase — KHÔNG cần đọc lại toàn bộ code. Cập nhật file này mỗi khi có thay đổi lớn.
>
> Cập nhật lần cuối: 2026-08-22 (kết thúc Phase 2).

---

## 1. Dự án là gì

Hệ thống **RAG (Retrieval-Augmented Generation)** cho phép người dùng (không chuyên luật) mô tả
tình huống giao thông bằng tiếng Việt → hệ thống tìm đúng điều luật liên quan → LLM tổng hợp câu
trả lời có **trích dẫn nguồn** (số hiệu, Điều, Khoản) + **nhãn độ tin cậy**. Giao diện chat.

- Nguyên tắc cốt lõi: **chỉ trả lời dựa trên văn bản luật thật, không bịa** (chống hallucination).
- Thêm luật mới = upload file, **không cần huấn luyện lại**.

**Đầu vào:** câu hỏi/tình huống tiếng Việt. **Đầu ra:** câu trả lời markdown + danh sách trích dẫn + độ tin cậy (cao/trung bình/thấp).

---

## 2. TRẠNG THÁI CÁC PHASE ⭐

Kế hoạch chia 5 phase (chi tiết: `docs/poc-phases.md`). Trạng thái hiện tại:

| Phase | Tên | Trạng thái | Nhánh git | Ghi chú |
|---|---|---|---|---|
| **1** | Core RAG Pipeline + Chat UI | ✅ **XONG** | `main` | Upload PDF → chunk → embed → vector search → LLM synthesis + trích dẫn; React chat UI |
| **2** | Hybrid Search (BM25 + RRF) | ✅ **XONG** | `feature/phase-2-hybrid` | Retrieval strategy hybrid; bắt exact-match (số Điều, con số) mà vector miss |
| **3** | Normalize câu không dấu | ⬜ **CHƯA LÀM** | — | Query step: LLM thêm dấu cho câu gõ không dấu trước khi search |
| **4a** | Enrich chunk (index-time) | ✅ **XONG** | `feature/phase-4-enrich` | Index step: LLM sinh câu hỏi đời thường gắn vào text-để-embed, tăng recall (chunk gốc giữ nguyên) |
| **4b** | Cross-verify (LLM 2) | ⬜ **CHƯA LÀM** | — | Query step `after_answer`: Gemini xác minh câu trả lời |
| **5** | UX hoàn thiện (auth, toàn văn, admin) | ⬜ **CHƯA LÀM** | — | Help-intent, xem toàn văn Điều, auth HMAC, admin login |

**Phụ thuộc:** tất cả build trên `main` (khung + Phase 1). Phase 2/3/4a/4b độc lập nhau (file rời). 4b nên đi cùng 2. Phase 5 cuối.
**Khung có sẵn trên `main`:** retrieval strategy (Phase 2), query step `before_retrieval`/`after_answer` (Phase 3/4b/5), **index step** (Phase 4a). Thêm phase = thêm file, bật qua `.env`.

### Trạng thái git (cập nhật 2026-08-22 — đã dọn nhánh, chuyển hẳn sang kiến trúc module)
- Remote: `https://github.com/NPhamDoan/RAG_GiaoThong`
- `main` = **trunk kiến trúc module**: khung (retrieval strategy + query step + **index step**) + Phase 1 + KB. **15 test**. Default `RETRIEVAL_STRATEGY=vector`, `INDEX_STEPS=`, `QUERY_STEPS=`.
- `feature/phase-2-hybrid` = `main` + đúng 2 file (`retrieval/hybrid_strategy.py` + test). 25 test. Bật: `RETRIEVAL_STRATEGY=hybrid`.
- `feature/phase-4-enrich` = `main` + đúng 2 file (`indexing/enrich_step.py` + test). 20 test. Bật: `INDEX_STEPS=enrich`.
- **Đã XÓA** nhánh cũ: `phase-1`, `phase-2`, `arch/step-plugin`, `core-module`.
- Thêm phase mới = tạo `feature/phase-N` **từ `main`**, chỉ THÊM file (xem mục 13). `git diff main feature/*` = đúng số file của phase.

---

## 3. Kiến trúc & Tech stack

```
[Frontend React]  --HTTP/JSON-->  [FastAPI backend]
                                     |
        Indexing: parse → chunk → embed → ChromaDB
        Query:    embed → hybrid search (vector+BM25+RRF) → gating → LLM synthesis → response
```

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| Frontend | React 19 + Vite + TypeScript + Tailwind v4 + axios + react-markdown + react-router | Chat UI, hiển thị markdown + trích dẫn bấm được |
| Backend | Python 3.11+ / FastAPI (async) | API, pipelines |
| Vector DB | ChromaDB (persistent, embedded) | Lưu + tìm vector; index cosine; collection `luat_giao_thong` |
| Embedding | sentence-transformers `intfloat/multilingual-e5-large` | Text → vector 1024 chiều; chạy CPU cục bộ |
| LLM synthesis | Groq API (`openai/gpt-oss-20b`) | Tổng hợp câu trả lời |
| LLM verify | Gemini (`gemini-2.0-flash`) | **Chưa dùng** — chuẩn bị cho Phase 4 |
| Parse PDF | PyMuPDF (fitz) | PDF → text; phát hiện scan (0 ký tự → reject) |
| Config | pydantic-settings + `.env` | Tham số tách khỏi code |

**Lưu ý môi trường:** máy dev đang chạy **Python 3.14** (rất mới). `requirements.txt` chỉ ghi min version nên pip kéo bản mới (torch 2.13, sentence-transformers 6.0...). Import chạy OK nhưng nếu gặp lỗi runtime lạ (nạp model...) thì nghi ngờ version mismatch đầu tiên.

---

## 4. Cấu trúc thư mục + vai trò file

```
backend/app/
├── main.py                 # FastAPI app; lifespan khởi tạo providers+pipelines; CORS(*); middleware log
├── config.py               # Settings (pydantic-settings), đọc backend/.env; get_settings() cached
├── logging_config.py       # Logger tập trung (console + file optional)
├── api/
│   ├── dependencies.py     # DI container: set/get singleton (query_pipeline, document_pipeline, vector_store)
│   └── routes/
│       ├── query.py        # POST /api/query
│       └── documents.py    # POST / GET / DELETE /api/documents
├── chunking/chunker.py     # VietnameseLawChunker: cắt theo "Điều N.", fallback 1200/overlap150, max 1800
├── models/schemas.py       # Pydantic: QueryRequest, KetQuaTraLoi, TrichDan, DocumentMetadataInput, IndexingResult
├── pipelines/
│   ├── document_pipeline.py# parse→validate→chunk→embed→store; DuplicateDocumentError; replace flag
│   └── query_pipeline.py   # embed→search(hybrid)→gating→synthesis→response; fallback khi LLM lỗi
├── prompts/system_prompts.py  # SYNTHESIS_SYSTEM_PROMPT (4 mục: Phân tích/Giải pháp/Căn cứ/Lưu ý)
├── providers/
│   ├── llm_provider.py         # ABC LLMProvider + LLMResponse
│   ├── embedding_provider.py   # ABC EmbeddingProvider
│   ├── groq_provider.py        # GroqProvider (AsyncGroq, temp 0.1, max_tokens 2048)
│   ├── gemini_provider.py      # GeminiProvider — CHƯA dùng (Phase 4)
│   └── huggingface_embedding.py# e5-large, lazy-load thread-safe, prefix query:/passage:, dim 1024
└── storage/vector_store.py # ChromaDB wrapper + [Phase 2] BM25 + RRF hybrid search

frontend/src/
├── App.tsx                 # Router: / → ChatPage, /admin → AdminPage
├── api/client.ts           # axios instance, baseURL = VITE_API_BASE_URL
├── hooks/{useQuery,useDocuments}.ts  # gọi /api/query ; upload/list/delete
├── pages/{ChatPage,AdminPage}.tsx
├── components/chat/{ChatInput,MessageList,MessageBubble,TrichDanItem,WelcomeSuggestions}.tsx
├── components/common/{AppLayout,ConfidenceBadge,DieuOverlay,LoadingIndicator}.tsx
└── types/index.ts          # TrichDan, KetQuaTraLoi, Message, DocumentMetadata, PaginatedDocuments

data/seed/                  # 3 PDF luật gốc (xem mục 8)
docs/                       # poc-phases.md, báo cáo Phase 1 & 2 (.md + .docx + script generate)
run_all.bat / run_backend.bat / run_frontend.bat / setup.bat / build.bat
```

---

## 5. Cách hoạt động

### 5.1. Indexing (nạp văn bản) — `document_pipeline.py`
1. Validate: ≤ 50MB; định dạng PDF/TXT; reject nếu trùng `soHieu` (trừ khi `replace=True`).
2. Parse: PyMuPDF đọc PDF → text; TXT decode UTF-8; PDF scan (0 ký tự) → lỗi.
3. Chunk: `VietnameseLawChunker` — 1 Điều = 1 chunk (regex `^Điều N[.:]`); fallback size ~1200/overlap 150; Điều > 1800 ký tự cắt nhỏ thêm.
4. Embed: e5-large với prefix `passage: `, batch, CPU.
5. Store: ChromaDB upsert (id `{soHieu}__dieu_{N}`, vector, text, metadata). **[Phase 2]** invalidate BM25 cache.

### 5.2. Query (trả lời) — `query_pipeline.py`
1. Embed câu hỏi với prefix `query: ` → vector 1024 chiều.
2. **[Phase 2] Hybrid search**: `store.search(vector, k=8, query_text=cauHoi)`.
3. Gating theo **điểm cosine cao nhất**:
   - `< 0.3` → "Không tìm thấy điều khoản phù hợp" (không gọi LLM).
   - `< 0.5` → "Không tìm thấy văn bản đủ liên quan" (không gọi LLM).
   - `≥ 0.5` → tiếp tục synthesis.
4. Synthesis: lấy tối đa **6 chunk** tốt nhất (mỗi chunk ≤ 2000 ký tự), đánh số [1..6], gửi Groq với `SYNTHESIS_SYSTEM_PROMPT`. Timeout 10s.
5. Đóng gói: câu trả lời markdown + `trichDan` + `doTinCay` (≥0.8 cao / ≥0.5 trung bình / <0.5 thấp).
6. Fallback: LLM lỗi/timeout → trả nguyên văn chunk gốc (`chunksGoc`) + trích dẫn.

### 5.3. [Phase 2] Hybrid Search — `vector_store.py`
- `search(query_vector, k, query_text=None)`: có `query_text` → `_hybrid_search`, không → `_vector_search` (như Phase 1).
- `_hybrid_search`:
  1. Vector: query Chroma lấy pool `max(k*4, 40)` ứng viên + điểm cosine.
  2. BM25: `_tokenize(query_text)` → `_BM25.search` lấy cùng số ứng viên.
  3. RRF merge (k=60): điểm = Σ `1/(60 + rank)` theo từng bảng.
  4. Sort theo RRF, lấy top-k (thứ tự này bắt exact-match).
  5. **Score trả về = cosine similarity** (đoạn BM25-only ngoài pool → `_cosine_for_ids` tính riêng). → Gating Phase 1 không đổi.
- `_BM25`: inverted index, Okapi BM25 (**k1=1.5, b=0.75**), IDF smoothing.
- `_tokenize`: lowercase → bỏ dấu (`_remove_diacritics`: NFD + đ→d) → tách token chữ/số (**giữ số**).
- Cache: `_ensure_bm25` dựng lười; `_invalidate_bm25` gọi khi `add_chunks`/`delete_by_so_hieu`.
- **Điểm mấu chốt:** RRF chỉ dùng để XẾP HẠNG; `score` vẫn là cosine → không phá gating/độ tin cậy.

---

## 6. API contract

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/api/query` | Body `{cauHoi}` (1..1000 ký tự) → `KetQuaTraLoi` | Công khai |
| POST | `/api/documents` | multipart: `file` + `metadata` (JSON) → `IndexingResult` (201). 409 nếu trùng, 400 nếu lỗi | Không (Phase 5 thêm) |
| GET | `/api/documents?page&page_size` | Danh sách văn bản (group theo soHieu) | Không |
| DELETE | `/api/documents/{soHieu}` | Xóa theo số hiệu (path cho phép `/`) | Không |

**`KetQuaTraLoi`**: `noiDung` (markdown), `trichDan[]` (`soHieu`,`tenVanBan`,`dieu`,`khoan`,`noiDungDayDu`), `doTinCay` ("cao"|"trung bình"|"thấp"), `chunksGoc` (chỉ khi LLM lỗi).

---

## 7. Config (`backend/.env`, xem `.env.example`)

| Key | Default | Ý nghĩa |
|---|---|---|
| `PRIMARY_LLM_PROVIDER` / `_MODEL` / `_API_KEY` | groq / `openai/gpt-oss-20b` / — | LLM synthesis (Groq). **Cần điền key** |
| `VERIFY_LLM_PROVIDER` / `_MODEL` / `_API_KEY` | gemini / `gemini-2.0-flash` / — | Verify (Phase 4, chưa dùng). Cần key khi làm Phase 4 |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | Model embedding (dim 1024) |
| `CHROMA_PERSIST_DIRECTORY` | `./data/chroma` | Thư mục lưu ChromaDB |
| `RETRIEVAL_TOP_K` | 8 | Số chunk lấy khi search |
| `SIMILARITY_THRESHOLD_MIN` / `_CONFIDENT` | 0.3 / 0.5 | Ngưỡng gating |
| `confidence_high_threshold` (code) | 0.8 | Ngưỡng "cao" |
| `synthesis_max_chunks` / `_max_chars_per_chunk` (code) | 6 / 2000 | Giới hạn đưa vào prompt |
| `primary_llm_timeout` (code) | 10s | Timeout LLM |

---

## 8. Dữ liệu nguồn (`data/seed/`)

| File | Văn bản |
|---|---|
| `36_2024_QH15_444251.pdf` | Luật Trật tự, An toàn giao thông đường bộ 2024 (luật chính) |
| `35_2024_QH15_588811.pdf` | Luật 35/2024/QH15 |
| `38_2024_TT-BGTVT_622477.pdf` | Thông tư 38/2024/TT-BGTVT (có phụ lục/bảng) |

Nạp qua Admin UI hoặc `POST /api/documents` kèm metadata (soHieu, tenVanBan, ngày ban hành/hiệu lực, cơ quan, loại).

---

## 9. Setup & Run (Windows / PowerShell)

```powershell
# Setup 1 lần (venv + deps backend, npm install frontend, tạo .env)
.\setup.bat            # hoặc làm tay:
#   backend:  python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
#   frontend: npm install
#   copy backend\.env.example backend\.env  → điền GROQ key

.\run_all.bat          # chạy backend (8000) + frontend (5173)
# hoặc: run_backend.bat / run_frontend.bat riêng
```
- Backend: http://localhost:8000 ; Frontend: http://localhost:5173
- Dùng `python -m uvicorn`, `python -m pip` (tránh .exe bị chặn).
- Venv đã tạo tại `backend/.venv`. `.env` đã tạo nhưng **API key còn placeholder** — synthesis fail tới khi điền Groq key.

**Chạy test tự động (pytest):**
```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # cài pytest (1 lần)
.\.venv\Scripts\python.exe -m pytest                                # main/phase-1: 12 test; phase-2: 21 test
```
- Cấu hình ở `backend/pytest.ini` (`testpaths = tests`). Test dùng fake Embedding/LLM + ChromaDB in-memory → nhanh (~2s), KHÔNG cần model 2GB hay gọi API.
- Cấu trúc: `tests/test_chunker.py`, `tests/test_vector_store.py` (vector-only), `tests/test_query_pipeline.py` (gating) = Phase 1; `tests/test_hybrid_search.py` = Phase 2 (chỉ `phase-2`); `tests/fakes.py` = fake dùng chung.

---

## 10. Quyết định thiết kế chính
- 1 Điều = 1 chunk (đơn vị pháp lý hoàn chỉnh, dễ trích dẫn).
- Embedding cục bộ (miễn phí, hỗ trợ tiếng Việt, không phụ thuộc API).
- ChromaDB nhúng (đơn giản, lưu đĩa, không cần server).
- Gating 2 mức để không gọi LLM khi thiếu dữ liệu (tiết kiệm + tránh bịa).
- Fallback trả chunk gốc khi LLM lỗi (luôn có kết quả).
- [Phase 2] BM25+RRF Python thuần (không thêm thư viện); giữ score = cosine để không đụng gating.
- Provider theo interface (ABC) → dễ đổi LLM/embedding qua `.env`.

---

## 11. Hạn chế hiện tại & Roadmap
| Hạn chế (sau Phase 2) | Xử lý ở |
|---|---|
| Câu gõ KHÔNG DẤU vào embedding vẫn kém (BM25 đã bỏ dấu, vector thì chưa) | Phase 3 |
| Chưa xác minh chéo câu trả lời LLM | Phase 4 (Gemini) |
| Chunk chưa enrich → recall câu đời thường còn yếu | Phase 4 |
| Không có auth: ai cũng upload/xóa | Phase 5 |
| Đã có unit test (pytest); chưa có eval retrieval trên dữ liệu thật (`check_retrieval.py` trong poc-phases) | (tùy chọn) |

---

## 12. Ghi chú cho session sau
- Đang ở nhánh `phase-2`. Muốn code Phase 3 → tạo nhánh mới từ `phase-1` (hoặc `main`) vì Phase 3 độc lập Phase 2; hoặc từ `phase-2` nếu muốn gộp cả 2.
- Báo cáo mỗi phase theo format: `docs/bao-cao-phaseN-poc.md` + `generate-bao-cao-phaseN-poc.py` (dùng python-docx, đã cài trong venv) → sinh `.docx`.
- Khi hoàn thành 1 phase: cập nhật **mục 2 (trạng thái phase)** và **mục 11** của file này.

---

## 13. Kiến trúc module/plugin + chiến lược delivery

> **Trạng thái:** ĐÃ là kiến trúc chính. `main` = trunk module (khung + Phase 1 + KB), default `RETRIEVAL_STRATEGY=vector`. `feature/phase-2-hybrid` = `main` + đúng 2 file Phase 2. `git diff main feature/phase-2-hybrid` = 2 file, 0 xoá. Các nhánh cũ (`phase-1`/`phase-2`/`arch/step-plugin`/`core-module`) đã xóa.
> Kích hoạt hybrid: đặt `RETRIEVAL_STRATEGY=hybrid` trong `.env` (không sửa code).

### Vì sao
Feature flag đơn thuần không chặn được khách bật phase chưa mua (code vẫn nằm trong bản giao). Kiến trúc module: **mỗi phase là file riêng**, bản giao chỉ copy file của phase đã bán → phase chưa giao **không có code để chạy**.

### Cấu trúc (trên `main`)
```
app/pipelines/query_pipeline.py   # orchestrator MỎNG: before_retrieval → embed → retrieval → answer → after_answer
app/pipelines/context.py          # QueryContext đi xuyên step
app/pipelines/steps/base.py       # QueryStep + StepDeps + load_steps (nạp động, step vắng file → bỏ qua)
app/retrieval/base.py             # RetrievalStrategy + load_strategy (nạp động theo config)
app/retrieval/vector_strategy.py  # Phase 1 (cosine)   [trên main]
app/retrieval/hybrid_strategy.py  # Phase 2 (BM25+RRF) [trên feature/phase-2-hybrid]
app/indexing/base.py              # IndexStep + IndexContext + load_index_steps [trên main]
app/indexing/enrich_step.py       # Phase 4a enrich    [trên feature/phase-4-enrich]
app/pipelines/document_pipeline.py# chạy index steps giữa chunk↔embed (chunk.text gốc vẫn store)
app/storage/vector_store.py       # storage THUẦN + primitives + data_version
```
- **3 loại điểm móc (đều trên `main`):**
  - Retrieval strategy — hoán đổi cách search (Phase 1 vector / Phase 2 hybrid), chọn qua `RETRIEVAL_STRATEGY`.
  - Query step — `before_retrieval(ctx)` (Phase 3 normalize, Phase 5 help-intent) + `after_answer(ctx)` (Phase 4b verify), bật qua `QUERY_STEPS`.
  - Index step — `process(ctx)` lúc index, sửa `embed_texts` (Phase 4a enrich), bật qua `INDEX_STEPS`.
- **Manifest** `.env`: `RETRIEVAL_STRATEGY=vector|hybrid`, `QUERY_STEPS=normalize,verify,...`, `INDEX_STEPS=enrich,...`.
- **BM25 cache** dùng `store.data_version` (tăng khi add/delete) để biết rebuild — thay cho callback.
- **Enrich** chỉ sửa text-để-embed; `chunk.text` gốc vẫn store → trích dẫn hiển thị sạch.

### Quy tắc vàng (để git merge tổ hợp không conflict)
Mỗi phase **tự chứa logic + prompt + config key trong CHÍNH file module của nó**, KHÔNG sửa file lõi chung (`query_pipeline.py`, `config.py`, `system_prompts.py`, `vector_store.py`). Phase không import lẫn nhau (giao tiếp qua `QueryContext`/interface).

### Tổ chức git cho delivery
- `main` = trunk: khung + Phase 1.
- `feature/phase-N` = từ `main`, **chỉ thêm file** của phase đó + test.
- `delivery/1-3-5` = từ `main`, `git merge` các feature cần → vì file rời nhau nên merge sạch. Đặt `.env` manifest + `git tag delivery-1.3.5`.
- Thêm phase mới = **thêm file module**, không sửa lõi.

### Việc tiếp theo
1. Làm Phase 3/4/5 = tạo `feature/phase-N` **từ `main`**, chỉ THÊM file step/strategy (không sửa lõi).
2. Giao tổ hợp: nhánh `delivery/*` merge các `feature/*` cần (file rời → merge sạch) + `.env` manifest + tag.
