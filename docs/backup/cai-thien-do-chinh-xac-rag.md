# KB — Các bước cải thiện độ chính xác RAG (tra cứu luật giao thông)

> Ghi lại theo dạng **Problem / Solution / Code fix** để xem lại và tái sử dụng.
> Bối cảnh: câu hỏi mẫu "vượt đèn đỏ phạt bao nhiêu" liên tục sai/thiếu. Truy vết qua 3 tầng:
> **retrieval → synthesis (LLM) → chunking**, cộng với cấu hình LLM.
>
> Dữ liệu test: Nghị định 168/2024/NĐ-CP (xử phạt) + Luật 35, 36/2024/QH15 + Thông tư 38/2024.
> Ground truth Điều→loại xe của ND168: **Điều 6=ô tô, 7=mô tô/xe máy, 8=xe máy chuyên dùng,
> 9=xe đạp/thô sơ, 10=người đi bộ**.

---

## 1) Groq trả về CONTENT RỖNG (model reasoning ăn hết token)

**Problem:** LLM chính là `openai/gpt-oss-20b` (Groq) — model REASONING. Với `max_tokens=2048`,
phần suy luận (reasoning tokens) ăn gần hết (vd `reasoning_tokens=2046/2048`, `finish_reason=length`)
→ `content` rỗng → pipeline rơi về fallback "LLM tạm thời không khả dụng".

**Solution:** Giảm mức suy luận bằng `reasoning_effort` và/hoặc tăng `max_tokens` đủ chỗ cho
cả suy luận LẪN câu trả lời. Cân bằng với giới hạn TPM (free-tier Groq = 8000: `prompt + max_tokens ≤ 8000`).

**Code fix:**
- `providers/groq_provider.py`: nhận `reasoning_effort`, truyền qua `extra_body` (an toàn mọi phiên bản SDK);
  log `finish_reason` + `reasoning_tokens` để chẩn đoán content rỗng.
- `.env`: preset **A** (nhẹ) `low`+`2048` hoặc preset **B** (chính xác) `medium`+`3500`.
- Commit: `f1bda95` (token fix), `f0b9bde` (2 preset trong `.env.example`).

---

## 2) Retrieval MISS câu đời thường ("vượt đèn đỏ")

**Problem:** Câu dân dã "vượt đèn đỏ" không kéo được điều khoản "không chấp hành hiệu lệnh của
đèn tín hiệu giao thông" vào top-k. Nguyên nhân: khoảng cách từ vựng đời thường ↔ pháp lý;
vector-only + chunk dài (điều khoản gộp nhiều hành vi) làm loãng tín hiệu.

**Solution:** **Enrich (Phase 4)** — lúc index, LLM sinh thêm *tóm tắt + từ khóa + câu hỏi đời thường*
kèm **cách gọi dân dã** rồi GẮN vào text-để-embed (giữ nguyên text gốc để hiển thị/trích dẫn).
Nhờ đó embed của chunk chứa "vượt đèn đỏ" → vector khớp câu dân dã.

**Code fix:**
- `indexing/enrich_step.py` — `_ENRICH_SYSTEM_PROMPT`: thêm quy tắc **phủ từng hành vi** (điểm a/b/c)
  + **bắt buộc cách gọi dân dã**, ví dụ:
  - "không chấp hành hiệu lệnh đèn tín hiệu" → "vượt đèn đỏ, vượt đèn vàng"
  - "nồng độ cồn" → "say xỉn, uống rượu bia lái xe"
  - "vượt quá tốc độ quy định" → "chạy quá tốc độ, chạy nhanh"
- Nhánh: `feature/phase-4-enrich`, commit `7728df1` + `750cc10`.
- **Lưu ý:** bật bằng `INDEX_STEPS=enrich` + cấu hình `ENRICH_LLM_*`; **phải seed lại** mới có tác dụng.
- Kiểm chứng: retrieval câu "vượt đèn đỏ" đưa chunk đèn tín hiệu vào top-8 (trước đó vắng mặt).

---

## 3) Synthesis (LLM) KHÔNG ánh xạ dân dã ↔ pháp lý

**Problem:** Kể cả khi chunk đúng ĐÃ vào ngữ cảnh, LLM vẫn trả "không có căn cứ" và hiểu nhầm
"vượt đèn đỏ" thành "vượt xe" (vượt phương tiện khác) → bỏ qua điều khoản đèn tín hiệu.

**Solution:** Dạy LLM ánh xạ cách gọi dân dã sang thuật ngữ pháp lý TRƯỚC khi kết luận "không có
căn cứ", và **quét hết** các đoạn, liệt kê **từng loại xe** với mức phạt đúng khoản.

**Code fix:** `prompts/system_prompts.py` — `SYNTHESIS_SYSTEM_PROMPT`:
- Quy tắc 7: phân biệt mức theo **loại xe**, liệt kê riêng từng loại.
- Quy tắc 8: ĐỐI CHIẾU cách gọi dân dã ↔ thuật ngữ pháp lý (vượt đèn đỏ = không chấp hành đèn tín hiệu,
  KHÁC "vượt xe"); nếu đoạn có hành vi tương ứng thì PHẢI dùng làm căn cứ.
- Quy tắc 9: QUÉT TẤT CẢ đoạn, liệt kê đầy đủ từng đối tượng; **chỉ gán mức phạt cho hành vi khi
  hành vi đó nằm TRONG chính khoản ghi mức đó** (chống lấy nhầm số từ khoản khác).
- Commit: `790a588` (quy tắc 7), `2d42fb2` (quy tắc 8), `40a6df1` (quy tắc 9). File lõi trên `main`.

---

## 4) Sai MỨC PHẠT do đúng khoản không lọt top-k (vector-only)

**Problem:** Với full data (597 chunk), câu "xe máy vượt đèn đỏ" → retrieval trả Điều 7 khoản 1,4
(không có khoản chứa đèn đỏ) → LLM chộp đại con số sai (vd 200k–400k / 800k–1tr) thay vì 6–8tr.

**Solution (2 phần):**
- **Hybrid search (Phase 2)** = vector + BM25 (Okapi) hợp nhất bằng RRF. BM25 bắt exact-match
  (số Điều, con số, từ khóa) mà vector bỏ sót → đúng khoản lọt top-k. `score` vẫn là cosine
  (không phá gating/độ tin cậy).
- **`reasoning_effort=medium`** giúp gpt-oss đọc kỹ, lấy đúng khoản (thay vì đọc lướt ở `low`).

**Code fix:**
- `retrieval/hybrid_strategy.py` (nhánh `feature/phase-2-hybrid`); bật bằng `RETRIEVAL_STRATEGY=hybrid`.
  Yêu cầu `vector_store` có primitives: `vector_search`, `get_corpus`, `cosine_for_ids`, `count`, `data_version`.
- `.env`: `RETRIEVAL_STRATEGY=hybrid`, `GROQ_REASONING_EFFORT=medium`, `LLM_MAX_TOKENS=3500`.
- Kết quả: câu "xe máy vượt đèn đỏ" → **6–8tr** (đúng), citation có Điều chứa đèn tín hiệu.

---

## 5) LLM gán NHẦM loại xe ↔ Điều (mức phạt của sai loại xe)

**Problem:** Khi nhiều Điều cùng có hành vi tương tự (đèn đỏ ở Điều 6/7/8/9; nồng độ cồn ở nhiều Điều),
LLM lấy mức của SAI loại xe. Vd:
- "ô tô vượt đèn đỏ" → trả 6–8tr (Điều 8 xe chuyên dùng) — SAI, đúng là Điều 6 (ô tô) ~18–20tr.
- "say rượu xe máy" → dùng Điều 9 (xe đạp) 150k–400k — SAI, đúng là Điều 7 (mô tô).

**Nguyên nhân gốc:** chunk cắt theo **khoản** → nhãn "loại xe" (nằm ở **tiêu đề Điều**, tức chunk đầu)
bị mất ở các chunk khoản sau. Chunk mức phạt không mang thông tin "áp dụng cho xe gì" → LLM đoán sai.

**Solution:** Gắn **tiêu đề Điều (chứa loại xe áp dụng)** vào MỖI sub-chunk khi một Điều dài bị cắt nhỏ.
Nhờ đó cả retrieval lẫn LLM đều biết chunk thuộc loại xe/Điều nào.

**Code fix:** `chunking/chunker.py`:
- `chunk_document`: lấy `dieu_header` = dòng đầu của Điều (vd "Điều 7. Xử phạt ... xe mô tô, xe gắn máy").
- `_chunks_by_size(..., header=...)`: prepend `header` vào chunk không bắt đầu bằng tiêu đề Điều.
- Commit: `82ea61f` (file lõi trên `main`). **Phải seed lại** (chunk đổi).
- Kiểm chứng: mọi sub-chunk của Điều 7 đều chứa "xe mô tô".

---

## 6) (Nền tảng) Cấu hình LLM dạng CATALOG + đa provider

**Problem:** `.env` rối; đổi model phải sửa nhiều dòng / bỏ comment từng model. Chỉ có Groq.

**Solution:** Catalog per-provider (điền key+model 1 lần) + selector `PRIMARY_LLM_PROVIDER` /
`VERIFY_LLM_PROVIDER` (chỉ điền TÊN). Thêm nhiều provider để thử nghiệm/độ bền quota.

**Code fix:**
- `config.py`: `LLMChoice` + `Settings.resolve_llm(provider)`; catalog `GROQ_*`, `MISTRAL_*`,
  `COHERE_*`, `GEMINI_*`, `OLLAMA_*` + `LLM_MAX_TOKENS`/`LLM_TIMEOUT`.
- `providers/llm_factory.py`: `create_primary_llm` + `create_verify_llm` dùng `resolve_llm` + `_build`.
- Providers mới: `mistral_provider.py` (`89f33f7`), `cohere_provider.py` (`fc1910b`); refactor catalog `d9481ec`.
- Fix model Gemini: `gemini-2.0-flash` (đã gỡ) → `gemini-3.6-flash` (`35f47f1`).
- Đã test 5/5 provider OK: groq, mistral, cohere, gemini, ollama.

---

## Thứ tự áp dụng khuyến nghị (khi gặp câu trả lời sai/thiếu)

1. **Đủ token + không rỗng** → chỉnh `reasoning_effort` + `max_tokens` (mục 1).
2. **Tìm được đúng điều khoản** → bật `enrich` (mục 2) + `hybrid` (mục 4).
3. **LLM hiểu đúng thuật ngữ** → prompt synthesis mục 3.
4. **Đúng loại xe** → chunker gắn tiêu đề Điều (mục 5).
5. Mỗi lần đổi chunk/enrich → **seed lại**; đổi prompt/config → **restart backend**.

## Công cụ kiểm chứng đã dùng
- Truy vấn `data/chroma/chroma.sqlite3` bằng sqlite: đếm chunk theo `soHieu`, xem `chroma:document`
  (text gốc), map Điều→loại xe, tìm khoản chứa "đèn tín hiệu" + mức phạt (ground truth).
- Script tạm: dump retrieval top-k (kiểm tra chunk + score), check enrich output, test từng provider.
- `ask.py "<câu hỏi>"` gọi API (cần backend chạy) để test end-to-end.

## Hạn chế còn lại
- Model nhỏ (`gpt-oss-20b`) vẫn có thể lẫn số Điều dù mức phạt đúng → cân nhắc model mạnh hơn /
  nâng Groq tier (nhiều TPM → tăng `RETRIEVAL_TOP_K`/`SYNTHESIS_MAX_CHUNKS`) / bật cross-verify (Gemini).
