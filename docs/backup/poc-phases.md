# POC Plan — Chia Phase (mỗi phase build + chạy được)

## Tổng kết nhanh

| Phase | Tên | Kết quả demo | Effort |
|---|---|---|---|
| 1 | Core RAG Pipeline | Upload PDF → search → LLM trả lời + trích dẫn | ~70% |
| 2 | Hybrid Search (BM25 + RRF) | Search chính xác hơn (exact match số Điều) | ~8% |
| 3 | Normalize câu không dấu | Gõ không dấu vẫn tìm đúng | ~5% |
| 4 | Enrich + Cross-verify | Recall tăng + badge "đã xác minh" | ~10% |
| 5 | UX hoàn thiện (help, toàn văn, admin) | App đầy đủ sản phẩm | ~7% |

---

## Phase 1: Core RAG Pipeline

**Mục tiêu:** App chạy E2E — upload file luật, hỏi câu hỏi, nhận câu trả lời có trích dẫn.

**Thành phần:**

| Module | Công việc | Library |
|---|---|---|
| Project setup | FastAPI + config (.env) + logging tập trung | fastapi, pydantic-settings, uvicorn |
| Parse file | PDF → text, TXT → text, reject scan PDF | pymupdf |
| Chunker | Regex `^Điều N[.:]` cắt chunk + fallback size 1200/overlap 150 | Python regex |
| Embedding | Load multilingual-e5-large, embed_text, embed_batch | sentence-transformers |
| Vector Store | ChromaDB wrapper: add_chunks, search (cosine top-k), delete | chromadb |
| Query Pipeline | Embed câu hỏi → search → gating (0.3/0.5) → LLM synthesis → response | groq |
| LLM Prompt | System prompt: 4 mục (Phân tích/Giải pháp/Căn cứ/Lưu ý) + citation [n] | — |
| Fallback | LLM lỗi/timeout → trả chunk gốc | — |
| API Routes | POST /api/query, POST /api/documents, GET /api/documents, DELETE /api/documents/{soHieu} | fastapi |
| Frontend | Chat UI: input → gọi API → render markdown + trích dẫn | react, vite, tailwind, axios, react-markdown |

**Demo khi xong Phase 1:**
- Upload "Bộ luật Dân sự 2015.txt" → hệ thống chunk + index
- Hỏi "điều kiện chuyển nhượng quyền sử dụng đất" → trả lời đúng + trích dẫn Điều

**Hạn chế:**
- Hỏi "Điều 650" → có thể miss (vector search yếu exact match số)
- Gõ không dấu → embedding kém → miss
- Từ đời thường ("chia tài sản khi bố mất") có thể không khớp thuật ngữ luật

---

## Phase 2: Hybrid Search — BM25 + RRF

**Mục tiêu:** Retrieval chính xác hơn — bắt được exact match + keyword mà vector search miss.

**Thêm gì:**

| Công việc | File | Code |
|---|---|---|
| Class `_BM25` (inverted index, TF-IDF Okapi) | `vector_store.py` | ~60 dòng |
| `_tokenize()` — bỏ dấu, giữ số | `vector_store.py` | ~10 dòng |
| `_hybrid_search()` — vector + BM25 + RRF merge (k=60) | `vector_store.py` | ~40 dòng |
| Sửa `search()` — gọi hybrid khi có query_text | `vector_store.py` | ~10 dòng |
| Invalidate BM25 cache khi add/delete | `vector_store.py` | ~10 dòng |

**Không thay đổi:** Frontend, API, prompt, config — chỉ search quality tăng.

**Demo khi xong Phase 2:**
- Hỏi "Điều 650 thừa kế" → Phase 1 miss, Phase 2 hit (BM25 khớp "650")
- Hỏi "tốc độ 60km/h khu dân cư" → hit đúng Điều 8 giao thông (BM25 khớp "60")

**Verify:** Chạy `check_retrieval.py` — bộ test case tự động.

---

## Phase 3: Normalize câu không dấu

**Mục tiêu:** User gõ không dấu → hệ thống tự thêm dấu trước khi search → recall tăng.

**Thêm gì:**

| Công việc | File | Code |
|---|---|---|
| `normalize_query()` — gọi LLM thêm dấu nếu câu thiếu dấu | `query_pipeline.py` | ~30 dòng |
| Safety guard: so sánh token set trước/sau, reject nếu LLM đổi từ | `query_pipeline.py` | ~15 dòng |
| `_has_vietnamese_diacritics()` — detect câu đã có dấu | `query_pipeline.py` | ~5 dòng |
| `NORMALIZE_SYSTEM_PROMPT` | `system_prompts.py` | ~20 dòng |
| Config: `normalize_llm_provider`, `normalize_llm_timeout` | `config.py` | ~5 dòng |

**Không thay đổi:** Search logic, frontend, LLM synthesis.

**Demo khi xong Phase 3:**
- Gõ "tim luat ve thua ke nha" → normalize → "tìm luật về thừa kế nhà" → search đúng
- Gõ "dieu kien chuyen nhuong dat" → normalize → "điều kiện chuyển nhượng đất" → hit

**Guard an toàn:** Nếu LLM đổi từ (không chỉ thêm dấu) → giữ câu gốc, không làm sai ý.

---

## Phase 4: Enrich chunk + Cross-verify

**Mục tiêu:** 
- Enrich: tăng recall — chunk embed phong phú hơn, match được cả câu hỏi informal
- Cross-verify: tăng độ tin cậy — LLM thứ 2 xác minh câu trả lời

**Thêm gì:**

| Công việc | File | Code |
|---|---|---|
| `_enrich_chunk()` — gọi LLM sinh tóm tắt/từ khóa/câu hỏi cho chunk | `document_pipeline.py` | ~20 dòng |
| `_build_embed_texts()` — embed text đã enrich, lưu text gốc | `document_pipeline.py` | ~25 dòng |
| `ENRICH_SYSTEM_PROMPT` | `system_prompts.py` | ~15 dòng |
| Config: `enrich_enabled`, `enrich_provider`, `enrich_model`, `ollama_base_url` | `config.py` | ~10 dòng |
| `_verify_answer()` — gọi Gemini xác minh, so sánh references | `query_pipeline.py` | ~60 dòng |
| `VERIFICATION_SYSTEM_PROMPT` | `system_prompts.py` | ~10 dòng |
| Frontend: `VerificationBadge` component | `VerificationBadge.tsx` | ~20 dòng |

**Lưu ý:**
- Enrich chỉ chạy lúc **seed** (nạp lại data) — cần Ollama local hoặc LLM API
- Cross-verify chạy **realtime** mỗi query — dùng Gemini (free 15 RPM)
- Gemini hết quota → graceful: trả "chưa xác minh" (không lỗi)

**Demo khi xong Phase 4:**
- Hỏi "bố mất chia tài sản" → hit chunk thừa kế (vì enriched text có câu hỏi tương tự)
- Mọi câu trả lời có badge: "đã xác minh" ✓ / "có mâu thuẫn" ⚠ / "chưa xác minh"

---

## Phase 5: UX hoàn thiện

**Mục tiêu:** App đầy đủ tính năng sản phẩm — help, xem toàn văn, admin, auth.

**Thêm gì:**

| Công việc | File | Code |
|---|---|---|
| Help-intent detection ("có thể hỏi gì?") → trả danh sách văn bản + gợi ý | `query_pipeline.py` | ~30 dòng |
| Toàn văn Điều ("full Điều 39") → gom chunk, trả nguyên văn | `query_pipeline.py` + `vector_store.py` | ~50 dòng |
| Auth: HMAC token, create/verify, admin login | `api/auth.py` + `api/routes/auth.py` | ~80 dòng |
| API documents: guard admin cho POST/DELETE | `api/routes/documents.py` | ~10 dòng |
| Frontend: LoginPage | `pages/LoginPage.tsx` | ~40 dòng |
| Frontend: AdminPage (upload + list + delete) | `pages/AdminPage.tsx` | ~100 dòng |
| Frontend: RequireAdmin guard + nav | `auth/` + `AppLayout.tsx` | ~40 dòng |
| Frontend: WelcomeSuggestions (màn chào + gợi ý) | `components/chat/WelcomeSuggestions.tsx` | ~30 dòng |

**Demo khi xong Phase 5:**
- Hỏi "hệ thống có gì?" → danh sách luật + gợi ý câu hỏi
- Hỏi "toàn văn Điều 39 luật đất đai" → trả nguyên văn Điều
- Admin đăng nhập → upload/xóa văn bản
- User thường chat không cần đăng nhập

---

## Dependency giữa các phase

```
Phase 1 (Core) ─────┐
                     │
Phase 2 (Hybrid) ───┤  ← build trên Phase 1, chỉ sửa vector_store
                     │
Phase 3 (Normalize) ─┤  ← build trên Phase 1, chỉ sửa query_pipeline
                     │
Phase 4 (Enrich+Verify) ┤  ← cần Phase 2 (hybrid search) để verify meaningful
                     │
Phase 5 (UX) ────────┘  ← cần Phase 1+2+3 đã ổn, thêm tính năng phụ
```

Phase 2 và 3 **không phụ thuộc nhau** — có thể làm song song hoặc đổi thứ tự.
Phase 4 nên sau Phase 2 (verify trên kết quả hybrid tốt hơn).
Phase 5 nên cuối (polish, không ảnh hưởng core logic).
