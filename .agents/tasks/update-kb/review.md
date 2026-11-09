# Review — Cập nhật KB project-kb.md

## Phạm vi
Thay đổi chưa commit duy nhất: `.kiro/steering/project-kb.md` (`git status --short` → chỉ ` M .kiro/steering/project-kb.md`, không có code ứng dụng nào đổi, không có commit mới). Đây là review độ chính xác tài liệu: đối chiếu từng khẳng định của KB với cây repo thực tế.

## Kiểm chứng tiêu chí nghiệm thu

- **Trạng thái git không còn nhánh feature/phase-***: ĐẠT. `git branch -r` chỉ có `origin/HEAD -> origin/main` và `origin/main`; `git branch` chỉ có `main`. KB (mục 2 "Trạng thái git") nói đúng "Chỉ còn 1 nhánh: main". Commit gần đây trong KB (`e06a56f`, `251760b`, `b10ee23`) khớp `git log --oneline -3`.
- **Danh sách providers khớp `app/providers/`**: ĐẠT. Thư mục có đủ `cohere_provider.py`, `mistral_provider.py`, `ollama_provider.py`, `gemini_provider.py`, `groq_provider.py`, `llm_factory.py`, `_http_base.py`, `huggingface_embedding.py`, `llm_provider.py`, `embedding_provider.py` — khớp mục 3 và mục 4. `llm_factory.py` có `create_primary_llm` và `_build`, KHÔNG có `create_verify_llm` → đúng như KB khẳng định (mục 3, 11, 12).
- **Mục 8 có Nghị định 168/2024/NĐ-CP**: ĐẠT. `data/seed/` có đúng 4 file, gồm `168_2024_ND-CP_619502.pdf`; cả 4 tên file khớp bảng mục 8.
- **Mục 9 con số test**: TỔNG đạt, PER-FILE sai (xem finding bên dưới). Tổng `def test_` trong `backend/tests/` = 39, khớp "Tổng 39 hàm test_" và "39 passed". `pytest.ini` có `testpaths = tests`, `pythonpath = .` khớp KB. Nhưng bảng phân rã per-file có 4/7 con số sai.
- **Trạng thái phase (mục 2) phản ánh đúng auth + enrich_io đã có file**: ĐẠT. `app/api/auth.py` có đủ `hash_password/verify_password/create_token/verify_token/require_admin`; `app/api/routes/auth.py` tồn tại (POST login); `app/indexing/enrich_io.py` tồn tại. Phase 5 ghi "PHẦN LỚN XONG" với auth ✓, Phase 4a "XONG" với enrich_io ✓.
- **Mục 6 API contract**: ĐẠT. `routes/documents.py` có đúng các route POST `""`, POST `/enrich-export-upload`, GET `""`, GET `/enrich-export`, PATCH `/{so_hieu:path}`, DELETE `/{so_hieu:path}`; route ghi đều có `Depends(require_admin)` — khớp bảng mục 6 (cột Auth).
- **Mục 11 hạn chế**: ĐẠT. Phản ánh đúng Phase 3/4b/5-help-intent chưa làm; `app/pipelines/steps/` chỉ có `base.py` (không có `normalize_step.py`/`verify_step.py`); config có `verify_llm_provider = "gemini"` nhưng không có `create_verify_llm`.
- **Dòng "Cập nhật lần cuối" = 2026-10-31**: ĐẠT.
- **.env.example defaults**: ĐẠT. `PRIMARY_LLM_PROVIDER=groq`, `VERIFY_LLM_PROVIDER=gemini`, `RETRIEVAL_STRATEGY` không set (KB nói mặc định vector — vector_strategy là default trong code/loader), `QUERY_STEPS`/`INDEX_STEPS` không set (rỗng), `ENRICH_SOURCE=llm`, các model/threshold khớp mục 7.
- **Chỉ project-kb.md bị sửa**: ĐẠT.

## Finding (blocker)

Bảng phân rã số test per-file ở mục 9 có 4/7 con số KHÔNG khớp số hàm `test_` thực tế trong `backend/tests/`:

| File | KB nói | Thực tế |
|---|---|---|
| test_query_pipeline.py | 5 | 6 |
| test_hybrid_search.py | 11 | 10 |
| test_enrich_step.py | 8 | 9 |
| test_enrich_io.py | 6 | 5 |

(3 file còn lại khớp: test_chunker 4, test_vector_store 2, test_document_pipeline 3.)

Tổng vẫn = 39 (các sai số bù trừ nhau) nên dòng "Tổng 39 hàm test_" và "39 passed" vẫn đúng, nhưng bảng per-file là khẳng định sai so với mã nguồn. Brief yêu cầu "con số khớp số hàm test_ trong tests/". Đây là review độ chính xác tài liệu nên con số phân rã sai là khẳng định bị phản chứng.

Hệ quả người đọc: người đọc KB tin sai số lượng test của từng module (ví dụ query_pipeline thực có 6 test gating/synthesis/fallback, hybrid thực có 10). Danh sách tên hàm thực tế đã liệt kê trong phần kiểm chứng bên dưới.

Sửa đề xuất (đặt đúng con số): test_query_pipeline.py (6), test_hybrid_search.py (10), test_enrich_step.py (9), test_enrich_io.py (5). Giữ nguyên 3 file kia và tổng 39.

### Bằng chứng tên hàm test_ (từ grep `^\s*def test_`)
- test_query_pipeline (6): test_no_results, test_below_min_threshold, test_below_confident_threshold, test_synthesis_medium_confidence, test_synthesis_high_confidence, test_fallback_when_llm_fails
- test_hybrid_search (10): test_remove_diacritics, test_tokenize_keeps_numbers_and_strips_diacritics, test_bm25_exact_match_ranks_first, test_bm25_no_match, test_hybrid_rescues_exact_match, test_hybrid_score_is_cosine, test_hybrid_no_query_text_falls_back_to_vector, test_bm25_cache_tracks_data_version, test_bm25_rebuilds_reflect_new_docs, test_query_text_passed_to_retrieval
- test_enrich_step (9): test_enrich_appends_to_embed_text_only, test_enrich_llm_failure_keeps_original, test_enrich_empty_chunks, test_build_returns_enrich_step, test_build_uses_dedicated_llm_from_env, test_build_unknown_provider_falls_back, test_enrich_through_document_pipeline, test_enrich_file_source_appends_from_file, test_enrich_file_missing_row_keeps_original
- test_enrich_io (5): test_export_only_selected_document, test_export_unknown_document_raises, test_parse_import_filtered_keeps_only_target_document, test_parse_import_filtered_no_matching_document_raises, test_parse_import_filtered_rejects_garbage

## Verdict
CHANGES_REQUESTED — một blocker: bảng số test per-file ở mục 9 có 4 con số bị phản chứng bởi mã nguồn. Mọi tiêu chí nghiệm thu khác đều đạt.
