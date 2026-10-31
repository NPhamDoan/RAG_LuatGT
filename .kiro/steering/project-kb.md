# PROJECT KB — RAG Tra cứu Luật Giao Thông Việt Nam

> Tài liệu ngữ cảnh dự án (knowledge base). Đọc file này là đủ hiểu dự án làm gì, kiến trúc,
> trạng thái từng phase — KHÔNG cần đọc lại toàn bộ code. Cập nhật file này mỗi khi có thay đổi lớn.
>
> Cập nhật lần cuối: 2026-10-31 (sau refactor gom LLM provider + factory, thêm auth admin, enrich auto/manual,
> sửa metadata văn bản; mọi phase đã gộp hẳn về `main`, dọn sạch nhánh feature/phase-*).

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

| Phase | Tên | Trạng thái | Vị trí | Ghi chú |
|---|---|---|---|---|
| **1** | Core RAG Pipeline + Chat UI | ✅ **XONG** | `main` | Upload PDF → chunk → embed → vector search → LLM synthesis + trích dẫn; React chat UI |
| **2** | Hybrid Search (BM25 + RRF) | ✅ **XONG** | `main` (`retrieval/hybrid_strategy.py`) | Retrieval strategy hybrid; bắt exact-match (số Điều, con số) mà vector miss. Bật `RETRIEVAL_STRATEGY=hybrid` |
| **3** | Normalize câu không dấu | ⬜ **CHƯA LÀM** | — | Query step `before_retrieval`: LLM thêm dấu cho câu gõ không dấu. **Chưa có file** `pipelines/steps/normalize_step.py` |
| **4a** | Enrich chunk (index-time) | ✅ **XONG** | `main` (`indexing/enrich_step.py` + `enrich_io.py`) | Index step: sinh câu hỏi đời thường gắn vào text-để-embed (chunk gốc giữ nguyên). Nguồn `llm` (auto) hoặc `file`/`manual`. Bật `INDEX_STEPS=enrich` |
| **4b** | Cross-verify (LLM 2) | ⬜ **CHƯA LÀM** | — | Query step `after_answer`: Gemini xác minh câu trả lời. **Chưa có file** `verify_step.py`. `verify_llm_provider` mới chỉ có trong config, chưa có `create_verify_llm` và chưa wire vào pipeline |
| **5** | UX hoàn thiện (auth, toàn văn, admin) | 🟡 **PHẦN LỚN XONG** | `main` | ✅ Auth admin (login HMAC + `require_admin` chặn route ghi), ✅ xem toàn văn Điều (`DieuOverlay`), ✅ lịch sử phiên chat (sidebar), ✅ sửa metadata văn bản (PATCH). ⬜ Help-intent (định tuyến câu hỏi hướng dẫn) chưa có step |

**Khung có sẵn trên `main`:** retrieval strategy (vector/hybrid), query step `before_retrieval`/`after_answer`,
**index step** (enrich). Thêm phase mới chưa làm (3 normalize, 4b verify, 5 help-intent) = thêm 1 file step/strategy,
bật qua `.env` — không sửa file lõi.

### Trạng thái git (cập nhật 2026-10-31 — đã gộp hẳn mọi phase về `main`)
- Remote: `https://github.com/NPhamDoan/RAG_LuatGT`
- **Chỉ còn 1 nhánh:** `main` (= `origin/main`). Các nhánh `feature/phase-2-hybrid`, `feature/phase-4-enrich`
  và các nhánh cũ (`phase-1`/`phase-2`/`arch/step-plugin`/`core-module`) **KHÔNG còn** trên remote.
- `main` chứa ĐẦY ĐỦ: khung module + Phase 1 + Phase 2 (hybrid) + Phase 4a (enrich) + Auth (Phase 5).
  Mặc định `.env.example`: `RETRIEVAL_STRATEGY=vector`, `QUERY_STEPS=` (rỗng), `INDEX_STEPS=` (rỗng),
  `ENRICH_SOURCE=llm`. Bật tính năng qua `.env`, không sửa code.
- Commit gần đây: `e06a56f update doc` · `251760b docs: dong bo tai lieu thiet ke voi code sau refactor`
  · `b10ee23 refactor: gom LLM provider, tach pipeline, don dead code + bo git provenance`.
- Kiến trúc "mỗi phase một file" vẫn giữ (xem mục 13) để có thể tách bản giao, nhưng hiện mọi file đã nằm
  trên `main` — không còn chiến lược nhiều nhánh feature song song.

---

## 3. Kiến trúc & Tech stack

```
[Frontend React]  --HTTP/JSON-->  [FastAPI backend]
                                     |
        Indexing: parse → chunk → (enrich) → embed → ChromaDB
        Query:    (steps) → embed → retrieval (vector | hybrid) → gating → LLM synthesis → (steps) → response
```

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| Frontend | React 19 + Vite + TypeScript + Tailwind v4 + axios + react-markdown + react-router | Chat UI, hiển thị markdown + trích dẫn bấm được, login admin, lịch sử phiên chat |
| Backend | Python 3.11+ / FastAPI (async) | API, pipelines |
| Vector DB | ChromaDB (persistent, embedded) | Lưu + tìm vector; index cosine; collection `luat_giao_thong` |
| Embedding | sentence-transformers `intfloat/multilingual-e5-large` | Text → vector 1024 chiều; chạy CPU cục bộ |
| LLM (factory) | `providers/llm_factory.py` → chọn 1 trong 5 provider theo `.env` | Mỗi vai trò (primary/verify) chỉ chọn TÊN provider; key+model lấy từ catalog |
| LLM providers | Groq (`openai/gpt-oss-20b`), Mistral (`mistral-small-latest`), Cohere (`command-r-08-2024`), Gemini (`gemini-3.6-flash`), Ollama (local, `qwen3:8b`) | Groq SDK; Mistral/Cohere qua HTTP (`_http_base.HttpLLMProvider`); Gemini SDK; Ollama HTTP local |
| Parse PDF | PyMuPDF (`import pymupdf as fitz`) | PDF → text; phát hiện scan (0 ký tự → reject) |
| Auth admin | stdlib: PBKDF2-HMAC-SHA256 (hash mật khẩu) + token HMAC có hạn | Bảo vệ route ghi (upload/sửa/xóa) |
| Config | pydantic-settings + `.env` | Tham số tách khỏi code; `extra=ignore` để bỏ qua env lạ |

**LLM factory (quan trọng):** `config.Settings.resolve_llm(name)` phân giải TÊN provider → `LLMChoice`
(lấy key/model/timeout từ catalog). `llm_factory.create_primary_llm(settings)` dựng provider cho vai trò
tổng hợp (`PRIMARY_LLM_PROVIDER`). **Chưa có `create_verify_llm`** — `VERIFY_LLM_PROVIDER` mới chỉ khai trong
config, dùng khi làm Phase 4b. Thêm provider mới = thêm nhánh trong `_build` (factory) + nhánh trong `resolve_llm`.

- `providers/_http_base.py`: `HttpLLMProvider` (base cho provider gọi Chat API qua HTTP — Mistral, Cohere) +
  tiện ích `build_messages` / `warn_if_empty` dùng chung.
- Groq là model REASONING → `GROQ_REASONING_EFFORT` (low/medium/high) + `LLM_MAX_TOKENS` phải đủ cho cả suy luận lẫn trả lời.

**Lưu ý môi trường:** máy dev đang chạy **Python 3.14** (rất mới). `requirements.txt` đã **PIN version (==)**
(fastapi 0.141.1, chromadb 1.5.9, groq 1.6.0, google-generativeai 0.8.6, sentence-transformers 6.0.0,
pymupdf 1.28.2, pydantic-settings 2.15.0, httpx 0.28.1...). Nếu gặp lỗi runtime lạ (nạp model...) thì nghi ngờ version mismatch đầu tiên.

---

## 4. Cấu trúc thư mục + vai trò file

```
backend/app/
├── main.py                 # FastAPI app; lifespan: embedding + llm_factory + ChromaDB + load_strategy/steps/index_steps;
│                           #   gắn router auth/query/documents; CORS(*); middleware log; cảnh báo nếu AUTH TẮT
├── config.py               # Settings (pydantic-settings) + LLMChoice + resolve_llm(); get_settings() cached
├── logging_config.py       # Logger tập trung (console + file optional)
├── api/
│   ├── auth.py             # hash_password/verify_password (PBKDF2), create_token/verify_token (HMAC), require_admin (dependency). `python -m app.api.auth "mk"` để tạo hash
│   ├── dependencies.py     # DI container: set/get singleton (query_pipeline, document_pipeline, vector_store, index_deps)
│   └── routes/
│       ├── auth.py         # POST /api/auth/login → token
│       ├── query.py        # POST /api/query
│       └── documents.py    # POST/GET/PATCH/DELETE /api/documents + enrich-export/-upload. Route GHI chặn bằng require_admin
├── chunking/chunker.py     # VietnameseLawChunker: cắt theo "Điều N.", fallback ~1200/overlap150, max 1800
├── models/schemas.py       # Pydantic: QueryRequest, KetQuaTraLoi, TrichDan, DocumentMetadataInput, DocumentUpdateInput, IndexingResult
├── pipelines/
│   ├── context.py          # QueryContext đi xuyên step
│   ├── document_pipeline.py# parse→validate→chunk→(index steps)→embed→store; enrich override per-request; seed metadata; chunk_only(); DuplicateDocumentError
│   ├── query_pipeline.py   # orchestrator mỏng: before_retrieval → embed → retrieval → _answer (gating+synthesis+fallback+dedupe) → after_answer
│   └── steps/base.py       # QueryStep (Protocol) + StepDeps + load_steps (nạp động, step vắng file → bỏ qua). CHƯA có step cụ thể nào
├── prompts/system_prompts.py  # SYNTHESIS_SYSTEM_PROMPT (4 mục) + SIMPLE_SYNTHESIS_SYSTEM_PROMPT (chọn qua SYNTHESIS_PROMPT=full|simple)
├── providers/
│   ├── llm_provider.py         # ABC LLMProvider + LLMResponse
│   ├── embedding_provider.py   # ABC EmbeddingProvider
│   ├── _http_base.py           # HttpLLMProvider (base HTTP) + build_messages/warn_if_empty
│   ├── llm_factory.py          # create_primary_llm(settings); _build(LLMChoice) → provider cụ thể
│   ├── groq_provider.py        # GroqProvider (AsyncGroq, reasoning_effort)
│   ├── mistral_provider.py     # MistralProvider (HTTP)
│   ├── cohere_provider.py      # CohereProvider (HTTP)
│   ├── gemini_provider.py      # GeminiProvider (SDK) — dùng khi làm Phase 4b
│   ├── ollama_provider.py      # OllamaProvider (HTTP local, think on/off)
│   └── huggingface_embedding.py# e5-large, lazy-load thread-safe, prefix query:/passage:, dim 1024
├── indexing/
│   ├── base.py                 # IndexStep (Protocol) + BaseIndexStep + IndexContext + IndexDeps + load_index_steps
│   ├── enrich_step.py          # Phase 4a: EnrichStep + build (nguồn llm/file) + build_auto + build_manual
│   └── enrich_io.py            # Export/Import enrich định dạng TEXT (khối "### CHUNK ... ###") cho tool ngoài
├── retrieval/
│   ├── base.py                 # RetrievalStrategy (ABC) + load_strategy (nạp động theo RETRIEVAL_STRATEGY)
│   ├── vector_strategy.py      # Phase 1 (cosine)
│   └── hybrid_strategy.py      # Phase 2 (BM25 + RRF)
└── storage/vector_store.py # ChromaDB storage THUẦN + primitives (vector_search, corpus, cosine_for_ids, count, data_version) + list/update/delete/exists

frontend/src/
├── App.tsx                 # Router: / → ChatPage, /login → LoginPage, /admin → AdminPage (bọc RequireAdmin)
├── main.tsx
├── api/client.ts           # axios instance, baseURL = VITE_API_BASE_URL, gắn Bearer token
├── auth/AuthContext.tsx    # lưu token + trạng thái đăng nhập admin
├── hooks/{useDocuments,useChatSessions}.ts  # upload/list/delete văn bản; quản lý phiên chat
├── pages/{ChatPage,AdminPage,LoginPage}.tsx
├── components/chat/{ChatInput,ChatSidebar,MessageList,MessageBubble,TrichDanItem,WelcomeSuggestions}.tsx
├── components/common/{AppLayout,ConfidenceBadge,DieuOverlay,LoadingIndicator,RequireAdmin}.tsx
├── utils/chatStorage.ts    # lưu lịch sử phiên chat (localStorage)
└── types/index.ts          # TrichDan, KetQuaTraLoi, Message, DocumentMetadata, PaginatedDocuments...

data/seed/                  # 4 PDF luật gốc (xem mục 8)
docs/                       # poc-phases.md, báo cáo Phase 1&2 (.md/.docx + script generate), cai-thien-do-chinh-xac-rag.md,
                            #   design/ (18 diagram drawio + PNG, tai-lieu-thiet-ke-he-thong.md/.docx, build.ps1, generate-docx.py, prepend-cover.py, Bia.docx)
run_all.bat / run_backend.bat / run_frontend.bat / setup.bat / build.bat
```

---

## 5. Cách hoạt động

### 5.1. Indexing (nạp văn bản) — `document_pipeline.py`
1. Validate: ≤ 50MB; định dạng PDF/TXT; reject nếu trùng `soHieu` (trừ khi `replace=True`).
2. Parse: PyMuPDF đọc PDF → text; TXT decode UTF-8; PDF scan (0 ký tự) → lỗi.
3. Chunk: `VietnameseLawChunker` — 1 Điều = 1 chunk (regex theo "Điều N."); fallback size ~1200/overlap 150; Điều > 1800 ký tự cắt nhỏ thêm.
4. **Index steps** (vd enrich): chạy giữa chunk↔embed, chỉ sửa `embed_texts`; `chunk.text` gốc giữ nguyên.
   `index_steps_override` (từ form Admin: `none`/`auto`/`manual`) ưu tiên hơn step mặc định (seed/CLI).
5. Embed: e5-large với prefix `passage: `, batch, CPU.
6. Store: ChromaDB upsert (id `{soHieu}__dieu_{N}`, vector từ embed_texts, text GỐC, metadata). Gắn `seed*` metadata per-document
   (nạp kiểu gì: enrich bật/tắt, nguồn/model, retrieval, embedding, thời điểm). Tăng `data_version` → invalidate BM25 cache.

### 5.2. Query (trả lời) — `query_pipeline.py` (orchestrator mỏng)
1. `before_retrieval(ctx)` cho từng query step (hiện CHƯA có step nào) — có thể short-circuit trả sớm.
2. Embed câu hỏi với prefix `query: ` → vector 1024 chiều.
3. Retrieval: `strategy.search(vector, top_k, cau_hoi)` — vector hoặc hybrid tùy `RETRIEVAL_STRATEGY`.
4. `_answer`: dedupe (gộp mảnh cùng `(soHieu, Điều)`) → gating theo **điểm cosine cao nhất**:
   - `< 0.3` → "Không tìm thấy điều khoản phù hợp" (không gọi LLM).
   - `< 0.5` → "Không tìm thấy văn bản đủ liên quan" (không gọi LLM).
   - `≥ 0.5` → synthesis.
5. Synthesis: lấy tối đa **6 chunk** tốt nhất (mỗi chunk ≤ `SYNTHESIS_MAX_CHARS_PER_CHUNK`, mặc định 5000), đánh số [1..N],
   gửi LLM với system prompt (`full` hoặc `simple` theo `SYNTHESIS_PROMPT`).
6. `after_answer(ctx)` cho từng query step (hiện chưa có step nào).
7. Đóng gói: câu trả lời markdown + `trichDan` + `doTinCay` (≥0.8 cao / ≥0.5 trung bình / <0.5 thấp).
8. Fallback: LLM lỗi/timeout → trả nguyên văn chunk gốc (`chunksGoc`) + trích dẫn.

### 5.3. Hybrid Search — `retrieval/hybrid_strategy.py` (+ primitives ở `vector_store.py`)
- `HybridStrategy.search(query_vector, k, query_text)`: có `query_text` → hybrid; không → vector-only.
- Quy trình: (1) vector lấy pool ứng viên + cosine; (2) BM25 trên `_tokenize(query_text)`; (3) RRF merge (k=60);
  (4) sort theo RRF lấy top-k (bắt exact-match); (5) **score trả về = cosine similarity** → gating/độ tin cậy Phase 1 KHÔNG đổi.
- `_BM25`: inverted index, Okapi BM25 (k1=1.5, b=0.75), IDF smoothing.
- `_tokenize`: lowercase → bỏ dấu (`_remove_diacritics`: NFD + đ→d) → tách token chữ/số (**giữ số**).
- Cache BM25 rebuild khi `store.data_version` đổi (store THUẦN, strategy tự quản cache — thay cho callback).

---

## 6. API contract

| Method | Path | Mô tả | Auth |
|---|---|---|---|
| POST | `/api/query` | Body `{cauHoi}` (1..1000 ký tự) → `KetQuaTraLoi` | Công khai |
| POST | `/api/auth/login` | Body `{password}` → `{token, role, expiresIn}`. 400 nếu auth chưa cấu hình, 401 nếu sai mật khẩu (delay ~1s) | Công khai |
| POST | `/api/documents` | multipart: `file` + `metadata` (JSON) + `enrich_mode` (none/auto/manual) + `enrich_file` (khi manual) → `IndexingResult` (201). 409 nếu trùng, 400 nếu lỗi | **require_admin** |
| POST | `/api/documents/enrich-export-upload` | multipart `file`+`metadata`: chunk PDF chưa nạp → file .txt để enrich ngoài | **require_admin** |
| GET | `/api/documents?page&page_size` | Danh sách văn bản (group theo soHieu) | Công khai |
| GET | `/api/documents/enrich-export?so_hieu=` | Xuất chunk của 1 văn bản đã nạp ra .txt (kèm prompt) để enrich ngoài | **require_admin** |
| PATCH | `/api/documents/{soHieu}` | Sửa metadata (tenVanBan/soHieu/loaiVanBan/coQuanBanHanh) — KHÔNG re-index. 404/409/400 | **require_admin** |
| DELETE | `/api/documents/{soHieu}` | Xóa theo số hiệu (path cho phép `/`) | **require_admin** |

**Auth:** `require_admin` kiểm tra header `Authorization: Bearer <token>`. Nếu `ADMIN_PASSWORD_HASH` TRỐNG → **auth TẮT**
(route ghi mở công khai, cảnh báo ở startup) để tiện dev. Token HMAC stateless có hạn `AUTH_TOKEN_TTL` (mặc định 8h).

**`KetQuaTraLoi`**: `noiDung` (markdown), `trichDan[]` (`soHieu`,`tenVanBan`,`dieu`,`khoan`,`noiDungDayDu`),
`doTinCay` ("cao"|"trung bình"|"thấp"), `chunksGoc` (chỉ khi LLM lỗi).

---

## 7. Config (`backend/.env`, xem `.env.example`)

### LLM catalog (khai 1 lần cho mỗi provider)
| Key | Default | Ý nghĩa |
|---|---|---|
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_REASONING_EFFORT` | — / `openai/gpt-oss-20b` / `medium` | Groq (reasoning model) |
| `MISTRAL_API_KEY` / `MISTRAL_MODEL` | — / `mistral-small-latest` | Mistral (HTTP) |
| `COHERE_API_KEY` / `COHERE_MODEL` | — / `command-r-08-2024` | Cohere (HTTP) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-3.6-flash` | Gemini (dùng khi Phase 4b) |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` / `OLLAMA_TIMEOUT` / `OLLAMA_THINK` | `http://localhost:11434` / `qwen3:8b` / 180 / false | Ollama local |
| `LLM_MAX_TOKENS` / `LLM_TIMEOUT` | 3500 / 30 | Tinh chung cho provider cloud |

### Chọn vai trò + query/index
| Key | Default | Ý nghĩa |
|---|---|---|
| `PRIMARY_LLM_PROVIDER` | `groq` | Provider LLM tổng hợp (groq\|mistral\|cohere\|gemini\|ollama) |
| `VERIFY_LLM_PROVIDER` | `gemini` | Provider verify — **mới chỉ có trong config, chưa dùng** (Phase 4b) |
| `RETRIEVAL_STRATEGY` | `vector` | `vector` (cosine) \| `hybrid` (vector+BM25+RRF) |
| `QUERY_STEPS` | (rỗng) | CSV query step, vd `normalize,verify` — hiện chưa có step nào có file |
| `INDEX_STEPS` | (rỗng) | CSV index step, vd `enrich` |
| `SYNTHESIS_PROMPT` | `full` | `full` \| `simple` (chọn system prompt synthesis) |

### Enrich (Phase 4a)
| Key | Default | Ý nghĩa |
|---|---|---|
| `ENRICH_SOURCE` | `llm` | `llm` (gọi LLM sinh enrich) \| `file` (đọc JSONL soạn sẵn) |
| `ENRICH_FILE` | (rỗng) | Đường dẫn JSONL khi `ENRICH_SOURCE=file` (tương đối so với gốc repo) |
| `ENRICH_LLM_PROVIDER` / `_MODEL` / `_API_KEY` | (rỗng) | LLM riêng cho enrich (groq\|ollama); trống = dùng LLM chính |
| `ENRICH_OLLAMA_BASE_URL` / `ENRICH_LLM_TIMEOUT` / `ENRICH_CONCURRENCY` / `ENRICH_OLLAMA_THINK` | `http://localhost:11434` / 120 / 3 / false | Tinh chỉnh enrich (các key này do `enrich_step` đọc riêng; Settings lõi `extra=ignore`) |

### Embedding / ChromaDB / gating / auth / log
| Key | Default | Ý nghĩa |
|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` | Model embedding (dim 1024) |
| `CHROMA_PERSIST_DIRECTORY` | `./data/chroma` | Thư mục lưu ChromaDB |
| `RETRIEVAL_TOP_K` | 8 | Số chunk lấy khi search |
| `SIMILARITY_THRESHOLD_MIN` / `_CONFIDENT` | 0.3 / 0.5 | Ngưỡng gating |
| `confidence_high_threshold` (code) | 0.8 | Ngưỡng "cao" |
| `synthesis_max_chunks` (code) / `SYNTHESIS_MAX_CHARS_PER_CHUNK` | 6 / 5000 | Giới hạn đưa vào prompt |
| `ADMIN_PASSWORD_HASH` | (rỗng) | Hash PBKDF2 mật khẩu admin. TRỐNG = TẮT auth. Tạo: `python -m app.api.auth "mk"` |
| `AUTH_SECRET_KEY` / `AUTH_TOKEN_TTL` | placeholder / 28800 | Khóa ký token (PHẢI đổi khi deploy) / hạn token (giây) |
| `LOG_LEVEL` / `LOG_FILE` / `LOG_PHASES` | `INFO` / (rỗng) / `all` | Mức log; file log; lọc trace theo phase (pipeline/normalize/enrich/verify...) |

---

## 8. Dữ liệu nguồn (`data/seed/`)

| File | Văn bản |
|---|---|
| `36_2024_QH15_444251.pdf` | Luật Trật tự, An toàn giao thông đường bộ 2024 (luật chính) |
| `35_2024_QH15_588811.pdf` | Luật 35/2024/QH15 |
| `38_2024_TT-BGTVT_622477.pdf` | Thông tư 38/2024/TT-BGTVT (có phụ lục/bảng) |
| `168_2024_ND-CP_619502.pdf` | Nghị định 168/2024/NĐ-CP (xử phạt vi phạm hành chính giao thông đường bộ) |

Nạp qua Admin UI hoặc `POST /api/documents` kèm metadata (soHieu, tenVanBan, ngày ban hành/hiệu lực, cơ quan, loại).

---

## 9. Setup & Run (Windows / PowerShell)

```powershell
# Setup 1 lần (venv + deps backend, npm install frontend, tạo .env)
.\setup.bat            # hoặc làm tay:
#   backend:  python -m venv .venv ; .\.venv\Scripts\python.exe -m pip install -r requirements.txt
#   frontend: npm install
#   copy backend\.env.example backend\.env  → điền key LLM (vd GROQ_API_KEY)

.\run_all.bat          # chạy backend (8000) + frontend (5173)
# hoặc: run_backend.bat / run_frontend.bat riêng
```
- Backend: http://localhost:8000 ; Frontend: http://localhost:5173
- Dùng `python -m uvicorn`, `python -m pip` (tránh .exe bị chặn).
- Nếu `.env` để `ADMIN_PASSWORD_HASH` trống → auth TẮT (route ghi mở, có cảnh báo khi startup).

**Chạy test tự động (pytest):**
```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt   # cài pytest (1 lần)
.\.venv\Scripts\python.exe -m pytest                                # 39 test, pass hết (~3s)
```
- Cấu hình ở `backend/pytest.ini` (`testpaths = tests`, `pythonpath = .`). Test dùng fake Embedding/LLM +
  ChromaDB in-memory → nhanh, KHÔNG cần model 2GB hay gọi API.
- **Kết quả đo thực tế (2026-10-31): 39 passed.** Test chạy được với các deps `pytest`, `chromadb`,
  `pydantic-settings`, `pymupdf`, `groq` (một vài test enrich import `groq_provider`). KHÔNG cần `sentence-transformers`
  (`huggingface_embedding` không được test import).
- Bố cục `tests/`: `test_chunker.py` (4), `test_vector_store.py` (2, vector-only), `test_query_pipeline.py` (6, gating/synthesis/fallback),
  `test_hybrid_search.py` (10, Phase 2), `test_document_pipeline.py` (3, index step), `test_enrich_step.py` (9, Phase 4a),
  `test_enrich_io.py` (5, export/import enrich), `fakes.py` (fake dùng chung). Tổng 39 hàm `test_`.

---

## 10. Quyết định thiết kế chính
- 1 Điều = 1 chunk (đơn vị pháp lý hoàn chỉnh, dễ trích dẫn).
- Embedding cục bộ (miễn phí, hỗ trợ tiếng Việt, không phụ thuộc API).
- ChromaDB nhúng (đơn giản, lưu đĩa, không cần server).
- Gating 2 mức để không gọi LLM khi thiếu dữ liệu (tiết kiệm + tránh bịa).
- Fallback trả chunk gốc khi LLM lỗi (luôn có kết quả).
- Hybrid BM25+RRF Python thuần (không thêm thư viện); giữ score = cosine để không đụng gating.
- **LLM factory + catalog:** đổi LLM cho một vai trò chỉ cần sửa TÊN provider trong `.env`; key/model khai 1 lần.
  Provider dùng chung `_http_base.HttpLLMProvider` nên thêm provider HTTP mới rất ngắn.
- Enrich chỉ sửa text-để-embed; `chunk.text` gốc vẫn store → trích dẫn hiển thị sạch. Nguồn enrich linh hoạt (llm/file/manual).
- Auth bằng stdlib (PBKDF2 + token HMAC) → không thêm thư viện; auth TẮT được khi dev.
- Provider/strategy/step theo interface (ABC/Protocol) + nạp động → dễ đổi qua `.env`, không sửa lõi.

---

## 11. Hạn chế hiện tại & Roadmap
| Hạn chế | Xử lý ở |
|---|---|
| Câu gõ KHÔNG DẤU vào embedding vẫn kém (BM25 đã bỏ dấu, vector thì chưa) | Phase 3 (normalize) — CHƯA làm |
| Chưa xác minh chéo câu trả lời LLM | Phase 4b (Gemini verify) — CHƯA làm (có config, chưa có step/factory) |
| Chưa có định tuyến help-intent (câu hỏi hướng dẫn sử dụng) | Phase 5 help-intent — CHƯA làm |
| Rate-limit login mới chỉ là delay ~1s; production nên đặt sau reverse proxy có rate-limit | (tùy chọn) |
| Có unit test (39, pass); chưa có eval retrieval trên dữ liệu thật | (tùy chọn) |

**Đã xử lý so với bản KB trước:** Phase 2 hybrid, Phase 4a enrich, auth admin + bảo vệ route ghi,
sửa metadata văn bản (PATCH), xem toàn văn Điều, lịch sử phiên chat, nhiều LLM provider + factory.

---

## 12. Ghi chú cho session sau
- Mọi phase đã nằm trên `main` (không còn nhánh feature). Làm phase mới (3 normalize / 4b verify / 5 help-intent)
  = THÊM 1 file step/strategy theo khung mục 13, bật qua `.env` — không sửa file lõi.
- Query step cần file `app/pipelines/steps/{name}_step.py` có hàm `build(deps)`; bật qua `QUERY_STEPS`.
  Index step cần `app/indexing/{name}_step.py` có `build(deps)`; bật qua `INDEX_STEPS`.
- Phase 4b verify: cần thêm `create_verify_llm` trong `llm_factory` (tái dùng `resolve_llm(VERIFY_LLM_PROVIDER)`)
  + step `after_answer`. Hiện `verify_llm_provider`/`GEMINI_*` đã sẵn trong config.
- Báo cáo phase theo format `docs/bao-cao-phaseN-poc.md` + `generate-bao-cao-phaseN-poc.py` (python-docx) → sinh `.docx`.
  Tài liệu thiết kế đầy đủ ở `docs/design/` (18 diagram drawio + PNG, `tai-lieu-thiet-ke-he-thong.md/.docx`, script build/render).
- Khi hoàn thành/đổi tính năng: cập nhật **mục 2 (trạng thái phase + git)**, **mục 6 (API)**, **mục 11 (hạn chế)** của file này.

---

## 13. Kiến trúc module/plugin

> **Trạng thái:** ĐÃ là kiến trúc chính và mọi file đã gộp về `main`. Giữ nguyên tắc "mỗi phase/tính năng mở rộng
> là 1 file module" để có thể tách bản giao nếu cần, nhưng hiện KHÔNG còn chiến lược nhiều nhánh feature song song.

### Vì sao
Mỗi tính năng mở rộng (strategy / query step / index step) là một file module nạp động theo `.env`.
Lõi KHÔNG phụ thuộc module cụ thể → bật/tắt bằng config, thêm tính năng mà không sửa file lõi,
và (nếu muốn) chỉ copy đúng file của phần đã bán cho một bản giao.

### Cấu trúc (trên `main`)
```
app/pipelines/query_pipeline.py   # orchestrator MỎNG: before_retrieval → embed → retrieval → answer → after_answer
app/pipelines/context.py          # QueryContext đi xuyên step
app/pipelines/steps/base.py       # QueryStep + StepDeps + load_steps (nạp động; step vắng file → bỏ qua)
app/retrieval/base.py             # RetrievalStrategy + load_strategy
app/retrieval/vector_strategy.py  # Phase 1 (cosine)
app/retrieval/hybrid_strategy.py  # Phase 2 (BM25 + RRF)
app/indexing/base.py              # IndexStep + IndexContext + IndexDeps + load_index_steps
app/indexing/enrich_step.py       # Phase 4a enrich (+ enrich_io.py cho export/import)
app/pipelines/document_pipeline.py# chạy index steps giữa chunk↔embed (chunk.text gốc vẫn store)
app/storage/vector_store.py       # storage THUẦN + primitives + data_version
app/providers/llm_factory.py      # chọn LLM provider theo config (catalog trong Settings)
```
- **3 loại điểm móc (đều trên `main`):**
  - Retrieval strategy — hoán đổi cách search (vector / hybrid), chọn qua `RETRIEVAL_STRATEGY`.
  - Query step — `before_retrieval(ctx)` (Phase 3 normalize, Phase 5 help-intent) + `after_answer(ctx)` (Phase 4b verify),
    bật qua `QUERY_STEPS`. **Hiện chưa có file step cụ thể nào.**
  - Index step — `process(ctx)` lúc index, sửa `embed_texts` (Phase 4a enrich), bật qua `INDEX_STEPS`.
- **Manifest** `.env`: `RETRIEVAL_STRATEGY`, `QUERY_STEPS`, `INDEX_STEPS` (+ `PRIMARY/VERIFY_LLM_PROVIDER`).
- **BM25 cache** dùng `store.data_version` (tăng khi add/delete) để biết rebuild — thay cho callback.
- **Enrich** chỉ sửa text-để-embed; `chunk.text` gốc vẫn store → trích dẫn hiển thị sạch.

### Quy tắc vàng
Mỗi module (strategy/step) **tự chứa logic + prompt + config key trong CHÍNH file của nó**, KHÔNG sửa file lõi chung
(`query_pipeline.py`, `document_pipeline.py`, `config.py`, `system_prompts.py`, `vector_store.py`). Module giao tiếp
qua `QueryContext`/`IndexContext`/interface, không import lẫn nhau. Nhờ vậy thêm/bớt tính năng là thêm/bớt file.

### Việc tiếp theo
1. Phase 3/4b/5-help-intent = tạo file step tương ứng (`normalize_step.py` / `verify_step.py` / `help_intent_step.py`),
   bật qua `.env`. Phase 4b cần thêm `create_verify_llm` trong factory.
2. Nếu cần bản giao giới hạn tính năng: copy đúng các file module đã chọn + `.env` manifest phù hợp.
