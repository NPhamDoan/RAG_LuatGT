# Backend source clarity & structure review — `backend/app`

Mục tiêu: làm source RÕ hơn (clarity + structure), không đổi tính năng. Phạm vi: `backend/app`
(api, pipelines, retrieval, storage, chunking, providers, indexing, prompts, models, config,
main, logging_config). Đây KHÔNG phải review diff — review toàn bộ source hiện tại trên `main`.

Tổng quan: codebase sạch hơn mức trung bình — có logger tập trung, interface provider rõ,
kiến trúc module/step mạch lạc, không có `print` lạc hay `except: pass` nuốt lỗi. Phần lớn
vấn đề nằm ở (1) 5 LLM provider lặp gần như nguyên khối, (2) vài god-function trong pipeline,
(3) scaffolding/dead code còn sót, (4) vài chỗ `except Exception` quá rộng, (5) magic number.

Watch for:
- **confirmed** — 5 provider (groq/mistral/cohere/gemini/ollama) lặp ~70% boilerplate: build
  messages, log request/response, cảnh báo content rỗng. Chưa unify → sửa 1 hành vi phải sửa 5 file.
- **confirmed** — `_git_info()` + `_seed_metadata()` trong `document_pipeline.py` là scaffolding
  "delivery/phase" không còn hợp cảnh; gọi `subprocess git` mỗi lần nạp văn bản.
- **confirmed** — Dead code: `create_verify_llm`, `BaseStep`, `StepDeps.verify_llm`,
  `apply_enrich_to_jsonl`/`parse_import_text` (chỉ test gọi), `embedding_dimension` (config khai mà không dùng).
- **confirmed** — Bug tiềm ẩn: `enrich_step.build_auto` đọc `deps.settings.primary_llm_api_key`
  — field này KHÔNG tồn tại trong `Settings` → luôn fallback "" âm thầm.
- **confirmed** — Comment tham chiếu "Phase 1/2/4", "nhánh feature/*", "golden rule" rải khắp file
  — không còn đúng (tất cả đã ở `main`), gây nhiễu người đọc mới.

**Verdict**: NEEDS_CHANGES

## High-level view

Năm LLM provider là nơi lặp nhiều nhất và đáng gom nhất: ba provider HTTP thuần (mistral,
cohere + phần lớn ollama) có cùng khung build messages → POST → raise_for_status → log, chỉ
khác URL, cách bóc content và tham số body. Một base class HTTP (hoặc helper build-messages +
log-content) xóa được phần lớn trùng lặp mà không đụng hành vi riêng của từng hãng.

`query_pipeline.py` nhìn chung tốt (orchestrator mỏng), nhưng `_answer` kiêm quá nhiều việc:
gating 2 mức, dedupe, chọn prompt, gọi LLM, fallback. Tách gating ra một helper trả quyết định
sẽ làm luồng dễ đọc hơn. `document_pipeline.process_document` là god-function 9 bước có đánh số
trong comment — dấu hiệu nên tách thành các bước private.

`vector_store.py` phần lớn gọn, nhưng `update_document_metadata` ôm hai nhánh rất khác nhau
(đổi soHieu = delete+upsert, không đổi = update) và lẫn chi tiết numpy; tách hai nhánh giúp đọc rõ.

Scaffolding delivery/phase (git info, seed manifest, comment "Phase N", "golden rule", "nhánh
feature/*") là gánh nặng nhận thức lớn nhất về mặt clarity: nó mô tả một mô hình giao hàng
nhiều nhánh mà repo hiện không còn dùng. Phần lớn có thể cắt hoặc rút gọn.

Có một nhóm dead code và một tham chiếu config sai (`primary_llm_api_key`) nên dọn để tránh
người đọc tưởng chúng đang hoạt động.

Naming nhìn chung tuân thủ quy ước (English verb + Vietnamese noun), chỉ lác đác chỗ trộn
chưa qua ranh giới camelCase hoặc tên viết tắt khó đoán.

<details>
<summary>Issues (16)</summary>

1. **5 provider lặp boilerplate** (High) — mistral/cohere/ollama (và phần build-messages của groq/gemini) lặp khung HTTP + log. Gom message-building + content-empty-warning vào helper hoặc base `HttpLLMProvider`.
2. **`_answer` god-function** (High) — gating + dedupe + prompt-select + synthesis + fallback trong một hàm. Tách `_gate(results)` trả quyết định, để `_answer` chỉ điều phối.
3. **`process_document` 9 bước đánh số** (High) — tách các bước (`_validate`, `_run_index_steps`, `_store_result`) thành private method; bỏ comment đánh số 1..9.
4. **Scaffolding git/seed trong document_pipeline** (High) — `_git_info()` chạy `subprocess git` mỗi lần nạp; `_seed_metadata()` ghi 10 field seed/phase. Đánh giá lại có cần không; nếu giữ, tách ra module riêng và bỏ nhánh/commit khỏi mỗi chunk.
5. **Comment tham chiếu Phase/nhánh/golden-rule** (High) — rải ở query_pipeline, retrieval, indexing, steps, config, hybrid_strategy. Cập nhật hoặc xóa — không còn đúng sau khi gộp về `main`.
6. **`primary_llm_api_key` không tồn tại** (High) — `enrich_step.build_auto` `getattr(deps.settings, "primary_llm_api_key", "")` luôn trả "". Dùng `groq_api_key` hoặc resolve qua `settings.resolve_llm`.
7. **Dead code: `create_verify_llm`** (Medium) — không nơi nào gọi (Phase 4 verify chưa wiring). Xóa hoặc đánh dấu rõ là chưa dùng.
8. **Dead code: `BaseStep` + `StepDeps.verify_llm`** (Medium) — `BaseStep` không ai kế thừa; `verify_llm` field không ai đọc. Xóa.
9. **Hàm chỉ test gọi: `apply_enrich_to_jsonl`, `parse_import_text`** (Medium) — route chỉ dùng `parse_import_filtered`/`build_export_*`. Xác nhận còn cần cho CLI; nếu không, xóa cùng test.
10. **`embedding_dimension` config không dùng** (Medium) — `get_dimension()` hardcode `1024`. Cho `get_dimension` đọc config, hoặc xóa field.
11. **`update_document_metadata` hai nhánh lẫn lộn** (Medium) — tách nhánh "đổi soHieu" (delete+upsert) khỏi nhánh "update tại chỗ"; comment numpy giữ lại.
12. **`except Exception` quá rộng** (Medium) — `_seed_metadata` (manifest_info), `verify_password`/`verify_token` (auth). Thu hẹp loại exception hoặc nêu rõ lý do bắt rộng.
13. **Magic number rải rác** (Medium) — `candidate_k = max(k*4, 40)` (hybrid), `_MAX_CHARS=1500` (enrich), `_PROGRESS_BATCH_SIZE=16`, `[:300]` cắt log, `[:120]`/`[:20]` so khớp text, `asyncio.sleep(1)` brute-force. Đặt tên có ý nghĩa / đưa lên config nếu cần chỉnh.
14. **Trùng khối build messages** (Medium) — đoạn `messages=[]; if system_prompt: append(system); append(user)` xuất hiện ở cả 5 provider + enrich. Rút thành helper dùng chung.
15. **Trùng dựng `DocumentMetadata`** (Low) — `process_document` và `chunk_only` copy y nguyên block map `DocumentMetadataInput → DocumentMetadata`. Tách `_to_document_meta(metadata)`.
16. **Naming lẻ chưa qua ranh giới camelCase / khó đoán** (Low) — `_b64e/_b64d`, `nm`/`m`/`emb` trong vector_store, `_trace(phase,...)` dùng "phase" như khái niệm log. Đổi tên rõ nghĩa hơn ở vài chỗ.

</details>

<details>
<summary>Details</summary>

### 5 LLM provider lặp boilerplate gần nguyên khối

`groq_provider.py`, `mistral_provider.py`, `cohere_provider.py`, `gemini_provider.py`,
`ollama_provider.py` cùng implement một interface tối giản (`generate(prompt, system_prompt)
→ LLMResponse`) nhưng lặp lại ba mảng code gần như giống hệt:

```
messages = []
if system_prompt:
    messages.append({"role": "system", "content": system_prompt})
messages.append({"role": "user", "content": prompt})
```

khối này nguyên văn trong groq, mistral, cohere, ollama (gemini ghép chuỗi thay vì messages) và
còn lặp lần nữa trong `enrich_step._enrich_one` gián tiếp. Sau đó mỗi provider lại lặp:
`logger.info("X request: model=%s, prompt_len=%d")` → `logger.debug(prompt)` → gọi API →
bóc content → `if not content: logger.warning("X trả CONTENT RỖNG...")` → `logger.debug(content)`.

mistral và cohere gần như song sinh: cùng `httpx.AsyncClient`, cùng headers Bearer, cùng
`raise_for_status`, cùng hai nhánh `except HTTPStatusError / HTTPError` log `resp.text[:300]`,
chỉ khác URL và cách bóc content (`choices[0].message.content` vs mảng block `{type,text}`).
Đây là ứng viên rõ nhất cho một base class:

```
class HttpLLMProvider(LLMProvider):          # pseudocode minh hoạ — KHÔNG phải code thật
    URL: str
    def _build_payload(self, messages) -> dict: ...
    def _extract_content(self, data) -> tuple[str, str|None]: ...  # (content, finish_reason)
    async def generate(...):   # build messages, POST, raise_for_status, log, warn-if-empty
```

mistral/cohere chỉ còn khai `URL`, `_build_payload`, `_extract_content`. ollama cần override
thêm (retry khi model không hỗ trợ `think`, strip `<think>`). groq (SDK) và gemini (SDK) không
dùng httpx nên không vào base HTTP, nhưng vẫn chia sẻ được helper `_build_messages()` và
`_warn_if_empty()`. Giá trị: một chỗ sửa format log / xử lý content rỗng thay vì năm chỗ; giảm
rủi ro lệch hành vi giữa provider (hiện ollama raise khi content rỗng còn mistral/cohere chỉ
warning — khác biệt này đang ẩn trong 5 file, khó nhận ra).

Lệch hành vi đáng lưu ý (confirmed): `ollama_provider` **raise RuntimeError** khi content rỗng,
trong khi mistral/cohere/groq/gemini chỉ **log warning rồi trả content rỗng**. Không nói đây là
sai, nhưng nó là một quyết định quan trọng đang nằm rải rác — gom về base sẽ buộc phải chọn một
chính sách nhất quán (hoặc cố ý override), thay vị để nó trôi theo từng file.

### `QueryPipeline._answer` ôm quá nhiều trách nhiệm

`_answer` (query_pipeline.py) làm năm việc trong một hàm: (1) chặn khi 0 kết quả, (2) dedupe,
(3) gating hai mức `< min` và `< confident`, (4) tính độ tin cậy + build prompt + gọi LLM,
(5) fallback khi LLM lỗi. Luồng gating bị xen kẽ với `_trace` nên thân hàm dài và khó đọc.

Tách phần quyết định gating ra một helper thuần (trả về "dừng/không đủ/tiếp tục" + max_score)
để `_answer` chỉ còn điều phối:

```
decision, max_score = self._gate(results)       # pseudocode minh hoạ
if decision is STOP:        return self._no_results()
if decision is WEAK:        return <không đủ liên quan>
# decision CONFIDENT → synthesis + fallback
```

Việc này cũng gom ba lần đọc `self._settings.similarity_threshold_*` vào một chỗ, và tách được
phần "LLM + fallback" thành hàm riêng dễ test.

### `process_document` là god-function 9 bước

`DocumentPipeline.process_document` dài ~70 dòng với comment đánh số `# 1. Validate size` …
`# 9. Store`. Chín bước tuần tự trong một hàm async là dấu hiệu nên tách: `_validate_upload`,
`_parse_and_chunk`, `_run_index_steps`, `_embed_and_store`. Comment đánh số là triệu chứng —
khi các bước thành method có tên, comment tự biến mất và thân `process_document` đọc như một
mục lục. `chunk_only` cũng lặp lại y nguyên block dựng `DocumentMetadata` từ `DocumentMetadataInput`
(9 field) — tách `_to_document_meta(metadata)` dùng chung cho cả hai.

### Scaffolding delivery/phase trong `document_pipeline.py`

`_git_info()` chạy `subprocess.run(["git", ...])` **mỗi lần nạp văn bản** để lấy branch + commit,
rồi `_seed_metadata()` nhét 10 field (`seedVersion`, `seedGitBranch`, `seedGitCommit`,
`seedIndexSteps`, `seedEnrichSource`...) vào metadata của **từng chunk**. Mục đích theo comment là
"truy ngược data thuộc delivery nào" — tức là tàn dư của mô hình giao hàng nhiều nhánh
(`feature/phase-*`, `delivery/*`) mô tả trong project KB. Trên một repo một-nhánh `main`, gọi git
subprocess trong hot path của indexing và nhân bản branch/commit vào mọi chunk là chi phí + nhiễu
không tương xứng. Đề xuất: đánh giá lại nhu cầu; nếu vẫn muốn ghi nguồn gốc, tách `_git_info`/
`_seed_metadata` ra module riêng (`indexing/provenance.py`) và lưu một lần ở cấp document thay vì
lặp vào từng chunk. Ít nhất nên bỏ git subprocess khỏi đường nạp (đọc một lần lúc startup).

### Comment tham chiếu Phase / nhánh / "golden rule" không còn đúng

Rải khắp source là các comment kiểu "Phase 1 vector / Phase 2 hybrid", "Dùng cho Phase 4",
"Chỉ đặt trên nhánh có Phase 4", "golden rule: không sửa file lõi", "Để git merge không đụng nhau".
Ví dụ: `query_pipeline.py` docstring, `retrieval/base.py`, `indexing/base.py`, `steps/base.py`,
`hybrid_strategy.py` ("Phase 2 —"), `vector_strategy.py` ("Phase 1 —"), `config.py`
(`retrieval_strategy # vector (Phase 1) | hybrid (Phase 2)`). Với người đọc mới, "Phase 2" và
"nhánh feature/*" là thuật ngữ nội bộ của một quy trình giao hàng đã kết thúc (mọi thứ đã ở
`main`). Chúng mô tả *lịch sử* chứ không mô tả *hành vi hiện tại*. Nên viết lại theo chức năng
("Hybrid retrieval: vector + BM25") và bỏ nhãn Phase/nhánh. Đây thuần là clarity, không đổi code.

### `enrich_step.build_auto` đọc setting không tồn tại

```python
api_key = cfg.enrich_llm_api_key.strip() or getattr(
    deps.settings, "primary_llm_api_key", ""
)
```

`Settings` không có field `primary_llm_api_key` (chỉ có `groq_api_key`, `mistral_api_key`, …).
`getattr(..., "")` nuốt mất sự thiếu vắng này → khi `ENRICH_LLM_PROVIDER=groq` mà
`ENRICH_LLM_API_KEY` trống, key luôn rỗng và lỗi chỉ lộ ra lúc gọi Groq. Đây là confirmed bug về
clarity/đúng đắn: hoặc dùng `deps.settings.groq_api_key`, hoặc resolve qua
`deps.settings.resolve_llm("groq").api_key`. Dùng `getattr` với default ở đây che giấu ý định.

### Dead code / scaffolding chưa dùng

- `create_verify_llm` (llm_factory.py): không nơi nào gọi; `main.py` chỉ gọi `create_primary_llm`.
  Verify (Phase 4b) chưa wiring. Để lại một hàm "sẵn sàng cho tương lai" là nhiễu — xóa hoặc
  chú thích rõ là chưa dùng.
- `BaseStep` (steps/base.py): không step nào kế thừa (enrich kế thừa `BaseIndexStep` ở indexing,
  khác file). `StepDeps.verify_llm` field: không ai đọc. Cả hai nên xóa.
- `apply_enrich_to_jsonl` và `parse_import_text` (enrich_io.py): route chỉ dùng
  `parse_import_filtered`, `build_export_text`, `build_export_from_chunks`. Hai hàm kia chỉ được
  `tests/test_enrich_io.py` gọi. Nếu còn phục vụ CLI seed thì giữ + ghi rõ; nếu không, xóa cùng test.
- `embedding_dimension: int = 1024` (config.py): `HuggingFaceEmbedding.get_dimension()` hardcode
  `return 1024`, không đọc config. Hoặc để `get_dimension` đọc `settings.embedding_dimension`,
  hoặc xóa field để tránh "hai nguồn sự thật" lệch nhau.

### `update_document_metadata` trộn hai nhánh rất khác nhau

Hàm có hai đường đi gần như không liên quan: đổi `soHieu` → `delete(old_ids)` + `upsert(new_ids,
embeddings)` (phải cast numpy → float thủ công), còn không đổi → `update(ids, metadatas)` tại chỗ.
Hai nhánh này có invariant khác nhau (một cái tái tạo id, một cái không) nhưng nằm chung một hàm
với comment numpy xen giữa. Tách `_rename_so_hieu(...)` và `_update_metas_in_place(...)` làm rõ
rằng chỉ nhánh rename mới đụng tới embedding/id.

### `except Exception` quá rộng ở vài chỗ

Phần lớn error handling trong repo tốt (log kèm context, không nuốt lỗi). Ba chỗ bắt quá rộng:

- `document_pipeline._seed_metadata`: `except Exception:` quanh `step.manifest_info()` rồi
  `logger.warning(... manifest_info() lỗi)`. Có log context nên không phải silent, nhưng bắt
  `Exception` trần cho một call khai báo metadata là quá rộng — một bug thật trong `manifest_info`
  sẽ bị che thành warning.
- `auth.verify_password` và `auth.verify_token`: `except Exception: return False`. Ở đây bắt rộng
  là *cố ý* (input không tin cậy, mọi lỗi parse → từ chối) — hợp lý về bảo mật, nhưng nên thu hẹp
  về `(ValueError, KeyError, binascii.Error)` hoặc thêm comment nêu rõ "bắt rộng có chủ đích: token
  do client gửi, mọi dị dạng = từ chối". Hiện không có comment nên trông giống nuốt lỗi.

`enrich_step._guarded` dùng `except Exception as exc` để gom lỗi từng chunk — đây là hợp lý (có
log kèm loại lỗi, không chặn cả mẻ) và nên giữ.

### Magic number nên đặt tên hoặc đưa lên config

- `hybrid_strategy.search`: `candidate_k = min(max(k * 4, 40), count)` — `4` và `40` là tham số
  tuning retrieval không tên. Đặt hằng `_CANDIDATE_POOL_MULTIPLIER = 4`, `_CANDIDATE_POOL_MIN = 40`.
- `enrich_step._MAX_CHARS = 1500`: có tên — nhưng ảnh hưởng chất lượng/chi phí enrich nên cân
  nhắc đưa lên `_EnrichSettings` để chỉnh được qua `.env`.
- `resp.text[:300]` (mistral/cohere), `[:120]`/`[:20]` (enrich `_text_matches`, chunker prepend
  header), `str(uuid4())[:8]` (main correlation_id): các lát cắt số thuần. `[:300]` lặp ở 2
  provider nên thành hằng `_ERR_BODY_PREVIEW` nếu gom provider.
- `auth.login`: `await asyncio.sleep(1)` — delay chống brute-force hardcode; đặt tên hoặc config.

### Naming — phần lớn đạt chuẩn, vài chỗ lẻ

Quy ước English-verb + Vietnamese-noun qua ranh giới camelCase được tuân thủ tốt: `process_query`,
`delete_by_so_hieu`, `build_citations`, `list_documents`, biến `so_hieu`, `cau_hoi`, `do_tin_cay`,
`ket_qua`. Một vài chỗ đáng chỉnh cho rõ:

- `vector_store.py`: biến một-chữ `nm`, `m`, `emb`, `cid` trong vòng lặp — ở hàm ngắn thì chấp
  nhận được, nhưng `update_document_metadata` đủ dài để `nm`/`m` nên là `new_meta`/`old_meta`.
- `auth._b64e` / `_b64d`: viết tắt khó đoán; `_b64_encode` / `_b64_decode` rõ hơn (chi phí thấp).
- `query_pipeline._trace(phase, ...)`: dùng từ "phase" cho một khái niệm log-namespace, trùng
  nghĩa với "Phase 1/2/4" ở chỗ khác → dễ nhầm. Cân nhắc đổi `phase` → `scope`/`tag`.

Không thấy vi phạm kiểu `newSoBanSao` (English modifier dính Vietnamese noun) — tốt.

</details>

<details>
<summary>File map</summary>

- `providers/{groq,mistral,cohere,gemini,ollama}_provider.py` — 5 provider lặp boilerplate; ứng viên gom base class HTTP + helper.
- `providers/llm_factory.py` — `create_verify_llm` dead code.
- `providers/huggingface_embedding.py` — `get_dimension` hardcode 1024.
- `pipelines/query_pipeline.py` — `_answer` god-function; comment Phase; `_trace(phase)` naming.
- `pipelines/document_pipeline.py` — `process_document` 9 bước; `_git_info`/`_seed_metadata` scaffolding; `except Exception` rộng; dựng `DocumentMetadata` lặp.
- `pipelines/steps/base.py` — `BaseStep`, `StepDeps.verify_llm` dead code.
- `storage/vector_store.py` — `update_document_metadata` hai nhánh lẫn; biến viết tắt.
- `retrieval/hybrid_strategy.py` — magic number `k*4`/`40`; comment "Phase 2".
- `retrieval/{base,vector_strategy}.py` — comment Phase/nhánh.
- `indexing/enrich_step.py` — `primary_llm_api_key` không tồn tại; comment "golden rule/Phase 4".
- `indexing/enrich_io.py` — `apply_enrich_to_jsonl`/`parse_import_text` chỉ test gọi.
- `indexing/base.py` — comment "golden rule/Phase 4".
- `api/auth.py` — `except Exception` auth (cố ý, thiếu comment); `_b64e/_b64d`; `sleep(1)` magic.
- `config.py` — `embedding_dimension` không dùng; comment Phase.

Không có full diff (đây là review toàn source, không phải PR).

</details>
