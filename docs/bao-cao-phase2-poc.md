# BÁO CÁO KHẢ THI — PHASE 2: Hybrid Search (BM25 + RRF)

*Hệ thống RAG Tra cứu Luật Giao Thông Việt Nam*

---

## 1. Bài toán

### 1.1. Vì sao cần Phase 2

Phase 1 tìm kiếm hoàn toàn bằng **vector (cosine similarity)**. Cách này hiểu tốt ngữ nghĩa ("chạy nhanh trong phố" ≈ "vượt quá tốc độ khu dân cư") nhưng lại **yếu với tìm chính xác theo từ khóa / con số**:

- Hỏi "Điều 650 thừa kế" → vector không ưu tiên con số "650", dễ trả về các Điều khác cùng chủ đề thừa kế.
- Hỏi "tốc độ 60km/h khu dân cư" → con số "60" bị embedding làm mờ, có thể miss đúng Điều quy định tốc độ.

Phase 2 bổ sung **tìm kiếm từ khóa (BM25)** chạy song song với vector, rồi hợp nhất hai bảng xếp hạng bằng **RRF (Reciprocal Rank Fusion)**. Kết quả: giữ nguyên khả năng hiểu nghĩa của vector, đồng thời bắt được exact-match mà vector bỏ sót.

### 1.2. Mục tiêu

- Tăng độ chính xác truy xuất (retrieval) — đặc biệt với số Điều, số hiệu văn bản, con số (km/h, kg...).
- **Không thay đổi** giao diện, API, prompt, cấu hình. Chỉ nâng chất lượng tầng tìm kiếm.
- Giữ nguyên logic gating và độ tin cậy của Phase 1 (ngưỡng 0.3 / 0.5 / 0.8).

### 1.3. Ràng buộc

| Ràng buộc | Chi tiết |
|---|---|
| Không đổi hợp đồng API | Frontend, endpoint, schema phản hồi giữ nguyên |
| Không đổi gating | Điểm số mỗi kết quả vẫn là cosine similarity để so ngưỡng |
| Không thêm dịch vụ ngoài | BM25 + RRF viết bằng Python thuần, không thêm thư viện, không gọi API |
| Hiệu năng | Chỉ mục BM25 dựng một lần, cache lại, dựng lại khi dữ liệu đổi |

---

## 2. Khái niệm nền tảng

### 2.1. Hạn chế của vector search (nhắc lại)

Vector search chuyển câu hỏi và đoạn luật thành vector rồi so độ tương đồng ngữ nghĩa. Vấn đề: con số và từ khóa hiếm ("650", "60km/h", "38/2024/TT-BGTVT") bị "hòa tan" vào nghĩa chung của câu, nên không được ưu tiên đúng mức. Đây chính là điểm yếu cần bù.

### 2.2. BM25 là gì?

**BM25 (Okapi BM25)** là thuật toán xếp hạng theo **từ khóa** (keyword) kinh điển trong tìm kiếm văn bản. Ý tưởng: một đoạn được coi là khớp nếu chứa **đúng các từ** trong câu hỏi, với ba yếu tố điều chỉnh:

- **TF (term frequency):** từ khóa xuất hiện càng nhiều trong đoạn → điểm càng cao (nhưng bão hòa dần, không tăng vô hạn).
- **IDF (inverse document frequency):** từ càng hiếm trong toàn bộ kho → càng quan trọng (vd "650" hiếm hơn "quy định").
- **Chuẩn hóa độ dài:** đoạn dài không bị lợi thế oan chỉ vì chứa nhiều từ.

Công thức dùng hai tham số chuẩn: **k1 = 1.5** (điều chỉnh độ bão hòa TF) và **b = 0.75** (mức chuẩn hóa độ dài). BM25 rất mạnh ở đúng chỗ vector yếu: **khớp chính xác từ khóa và con số.**

### 2.3. Inverted index (chỉ mục ngược)

Để BM25 chạy nhanh, ta dựng **inverted index**: bản đồ từ mỗi *token* → danh sách các đoạn chứa token đó (kèm số lần xuất hiện). Khi truy vấn, chỉ cần duyệt các đoạn chứa token trong câu hỏi thay vì quét toàn bộ kho.

### 2.4. Tokenize + bỏ dấu

Trước khi lập chỉ mục, văn bản được **tokenize**:

- Chuyển thường (lowercase).
- **Bỏ dấu tiếng Việt** ("Điều" → "dieu", "thừa kế" → "thua ke"), để câu gõ có dấu / không dấu vẫn khớp cùng token.
- **Giữ nguyên chữ số** ("650", "60") — đây là phần quan trọng nhất giúp bắt exact-match.

Ví dụ: `"Điều 650 thừa kế"` → `["dieu", "650", "thua", "ke"]`.

### 2.5. RRF là gì? (Reciprocal Rank Fusion)

Sau khi có **hai bảng xếp hạng** (một của vector, một của BM25), cần gộp lại thành một danh sách duy nhất. **RRF** làm việc này dựa trên **thứ hạng** chứ không dựa trên điểm số thô (vì điểm cosine và điểm BM25 không cùng thang đo).

Với mỗi đoạn, điểm RRF = tổng của `1 / (k + thứ_hạng)` trên từng bảng mà nó xuất hiện, với hằng số **k = 60** (giá trị chuẩn theo paper Cormack 2009):

- Đoạn đứng đầu ở cả hai bảng → điểm RRF cao nhất.
- Đoạn chỉ BM25 bắt được (vector miss) vẫn được cộng điểm → có cơ hội lọt top.
- Hằng số k = 60 làm mượt: giảm ảnh hưởng của chênh lệch thứ hạng ở đuôi danh sách.

RRF đơn giản, không cần huấn luyện, và là chuẩn công nghiệp để trộn nhiều nguồn xếp hạng.

### 2.6. Vì sao "hybrid" tốt hơn từng cái riêng

| Truy vấn | Vector đơn thuần | BM25 đơn thuần | Hybrid (RRF) |
|---|---|---|---|
| "chạy nhanh trong phố" (ngữ nghĩa) | Tốt | Kém (khác từ) | Tốt |
| "Điều 650" (exact-match) | Kém | Tốt | Tốt |
| "tốc độ 60km/h khu dân cư" | Trung bình | Tốt ("60") | Tốt |

Hybrid lấy điểm mạnh của cả hai: vector lo phần *nghĩa*, BM25 lo phần *chữ và số*.

---

## 3. Cách tiếp cận chi tiết

### 3.1. Kiến trúc tầng tìm kiếm sau Phase 2

Toàn bộ thay đổi gói gọn trong tầng lưu trữ (`vector_store.py`). Khi query pipeline gọi tìm kiếm và **có kèm nội dung câu hỏi** (`query_text`), hệ thống chạy nhánh hybrid; nếu không, vẫn chạy vector-only như Phase 1.

### 3.2. Quy trình Hybrid Search

| Bước | Tên | Xử lý cụ thể |
|---|---|---|
| 1 | Lấy ứng viên vector | Truy vấn ChromaDB lấy pool rộng `max(k×4, 40)` đoạn gần nhất kèm điểm cosine |
| 2 | Lấy ứng viên BM25 | Tokenize câu hỏi → tra inverted index → xếp hạng BM25, lấy cùng số ứng viên |
| 3 | Hợp nhất bằng RRF | Với mỗi đoạn, cộng `1/(60 + thứ_hạng)` theo từng bảng nó xuất hiện → điểm RRF |
| 4 | Chọn top-k theo RRF | Sắp xếp theo điểm RRF, lấy k đoạn đầu (thứ tự này bắt được exact-match) |
| 5 | Gán điểm cosine | Mỗi kết quả giữ điểm **cosine similarity** (đoạn BM25-only ngoài pool vector → tính cosine riêng từ embedding) |

**Điểm mấu chốt về gating:** RRF chỉ quyết định **thứ tự** kết quả. Trường `score` của mỗi kết quả **vẫn là cosine similarity** — nhờ vậy toàn bộ logic chặn kết quả kém (0.3 / 0.5) và tính độ tin cậy (0.8 / 0.5) của Phase 1 **không phải sửa gì**.

### 3.3. Ví dụ minh họa (đã kiểm chứng)

Với câu hỏi "Điều 650 thừa kế", trong tình huống vector xếp Điều 650 **đứng cuối**:

- Vector-only: `[Điều 1, Điều 9, Điều 8, Điều 650]` — Điều 650 bị đẩy xuống cuối.
- Hybrid: `[Điều 1, Điều 650, Điều 9, Điều 8]` — BM25 khớp token "650" đẩy Điều 650 lên hạng 2.

Điểm cosine vẫn được bảo toàn cho từng kết quả, nên gating hoạt động bình thường.

### 3.4. Cache chỉ mục BM25

- Inverted index được **dựng lười (lazy)** ở lần tìm kiếm hybrid đầu tiên, rồi **cache** trong bộ nhớ.
- Khi kho dữ liệu thay đổi (thêm văn bản `add_chunks`, xóa văn bản `delete_by_so_hieu`), cache bị **vô hiệu hóa** để lần tìm kiếm kế tiếp dựng lại từ dữ liệu mới.
- Với quy mô POC (vài văn bản, vài trăm đoạn), chi phí dựng lại không đáng kể.

### 3.5. Quyết định thiết kế

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Thuật toán từ khóa | BM25 Okapi (k1=1.5, b=0.75) | Chuẩn công nghiệp; mạnh ở exact-match; không cần huấn luyện |
| Cách trộn xếp hạng | RRF (k=60) | Gộp theo thứ hạng, không phụ thuộc thang điểm; đơn giản, ổn định |
| Tokenize | Bỏ dấu + giữ số | Câu có/không dấu cùng token; giữ số để bắt "650", "60" |
| Điểm trả về | Giữ cosine similarity | Không phá gating & độ tin cậy của Phase 1 |
| Pool ứng viên | `max(k×4, 40)` | Đủ rộng để hai nguồn có phần giao nhau cho RRF |
| Cache BM25 | Dựng lười + vô hiệu khi add/delete | Tránh dựng lại mỗi truy vấn; luôn nhất quán với dữ liệu |
| Cài đặt | Python thuần (không thư viện mới) | Nhẹ, không thêm phụ thuộc, dễ bảo trì |

---

## 4. Thay đổi mã nguồn

Phase 2 chỉ chạm **2 file**, đúng như phạm vi thiết kế.

### 4.1. `backend/app/storage/vector_store.py`

| Thành phần thêm/sửa | Mô tả |
|---|---|
| `_remove_diacritics()` | Bỏ dấu tiếng Việt (NFD + xử lý đ/Đ), giữ chữ và số |
| `_tokenize()` | Lowercase → bỏ dấu → tách token chữ/số (giữ con số) |
| `class _BM25` | Inverted index + Okapi BM25 (k1=1.5, b=0.75); hàm `search()` trả top-k |
| `_ensure_bm25()` / `_invalidate_bm25()` | Dựng lười + vô hiệu hóa cache chỉ mục BM25 |
| Tách `search()` | Thành `_vector_search()` (như cũ) và `_hybrid_search()` (vector + BM25 + RRF) |
| `_cosine_for_ids()` / `_cosine()` | Tính cosine cho đoạn BM25-only nằm ngoài pool vector |
| Hook vào `add_chunks` / `delete_by_so_hieu` | Gọi `_invalidate_bm25()` sau khi corpus đổi |

### 4.2. `backend/app/pipelines/query_pipeline.py`

| Thay đổi | Mô tả |
|---|---|
| Truyền `query_text` | Gọi `search(query_vector, k=..., query_text=cau_hoi)` để kích hoạt nhánh hybrid |

**Không đổi:** frontend, API routes, schema, system prompt, config (`.env`).

---

## 5. Kiểm chứng

| Hạng mục | Cách kiểm | Kết quả |
|---|---|---|
| Tokenize giữ số + bỏ dấu | `"Điều 650 thừa kế"` → token | `["dieu","650","thua","ke"]` đúng |
| BM25 exact-match | Corpus 3 đoạn, truy vấn "Điều 650 thừa kế" | Đoạn chứa "650" xếp hạng 1 |
| Hybrid cứu exact-match | Vector xếp Điều 650 cuối → chạy hybrid | Điều 650 lên hạng 2 (cao hơn vector-only) |
| Bảo toàn cosine cho gating | Kiểm tra `score` mỗi kết quả | Nằm trong [-1, 1], đúng cosine |
| Vô hiệu cache khi xóa | `delete_by_so_hieu` sau khi đã dựng index | Cache BM25 bị clear, dựng lại lần sau |
| Import 2 module | Nạp `vector_store`, `query_pipeline` | OK, không lỗi |

---

## 6. Công nghệ sử dụng

Phase 2 **không thêm thư viện hay dịch vụ mới**. BM25, tokenize và RRF đều viết bằng thư viện chuẩn của Python.

| Thành phần | Công nghệ | Ghi chú |
|---|---|---|
| BM25 + inverted index | Python thuần (`math`) | Okapi BM25, k1=1.5, b=0.75 |
| Bỏ dấu tiếng Việt | `unicodedata` (chuẩn hóa NFD) | Xử lý riêng đ/Đ |
| Tokenize | `re` (regex) | Tách token chữ/số |
| RRF merge | Python thuần | Hằng số k=60 |
| Vector search | ChromaDB (giữ nguyên Phase 1) | Cosine similarity |

---

## 7. Kết luận tính khả thi Phase 2

| Khía cạnh | Đánh giá | Ghi chú |
|---|---|---|
| Kỹ thuật | Khả thi cao | BM25 + RRF là kỹ thuật chuẩn, cài đặt gọn bằng Python thuần |
| Phạm vi | Nhỏ, cô lập | Chỉ 2 file; không đụng API/frontend/prompt/config |
| Rủi ro | Thấp | Giữ nguyên gating; có nhánh vector-only dự phòng |
| Chất lượng | Tăng rõ | Bắt được exact-match (số Điều, con số) mà Phase 1 miss |
| Mở rộng | Dễ | Nền tảng tốt cho Phase 4 (verify trên kết quả hybrid) |

### 7.1. Hạn chế còn lại (chuyển sang các Phase sau)

| Hạn chế | Hướng xử lý |
|---|---|
| Câu gõ không dấu vào embedding vẫn kém (BM25 đã bỏ dấu nhưng vector thì chưa) | Phase 3 — normalize câu không dấu bằng LLM |
| Chưa xác minh chéo câu trả lời của LLM | Phase 4 — cross-verify bằng LLM thứ 2 |
| Chunk chưa được làm giàu (enrich) để tăng recall câu hỏi đời thường | Phase 4 — enrich chunk khi seed |
| Chưa có xác thực cho upload/xóa | Phase 5 — auth + admin |

---

## 8. Phụ thuộc giữa các Phase

```
Phase 1 (Core) ─────┐
                     │
Phase 2 (Hybrid) ───┤  ← build trên Phase 1, chỉ sửa vector_store + query_pipeline
                     │
Phase 3 (Normalize) ─┤  ← build trên Phase 1, độc lập Phase 2
                     │
Phase 4 (Enrich+Verify) ┤  ← nên sau Phase 2 (verify trên hybrid tốt hơn)
                     │
Phase 5 (UX) ────────┘  ← cuối cùng, thêm tính năng phụ
```

Phase 2 làm chồng trực tiếp lên Phase 1. Nhánh `phase-2` chứa toàn bộ Phase 1 cộng thêm phần Hybrid Search.
