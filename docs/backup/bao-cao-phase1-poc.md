# BÁO CÁO KHẢ THI — PHASE 1: Core RAG Pipeline + Chat UI

*Hệ thống RAG Tra cứu Luật Giao Thông Việt Nam*

---

## 1. Bài toán

### 1.1. Mô tả bài toán

Xây dựng hệ thống cho phép người dùng (không chuyên luật) mô tả tình huống giao thông thực tế bằng tiếng Việt, hệ thống tự động tìm đúng điều luật liên quan rồi tổng hợp câu trả lời có căn cứ pháp lý kèm trích dẫn nguồn cụ thể. Giao diện chat trực quan, dễ sử dụng.

### 1.2. Đầu vào / Đầu ra

**Đầu vào:** Câu hỏi / mô tả tình huống giao thông bằng tiếng Việt.

**Đầu ra:** Câu trả lời tổng hợp kèm trích dẫn (số hiệu văn bản, Điều, Khoản), chỉ số độ tin cậy, hiển thị trên giao diện chat.

### 1.3. Ràng buộc

- Bám sát văn bản: chỉ trả lời dựa trên văn bản luật thật, không bịa nội dung
- Hỗ trợ tiếng Việt: thuật ngữ pháp lý lẫn đời thường
- Trích dẫn nguồn rõ ràng (số hiệu, Điều, Khoản)
- Phản hồi < 5 giây
- Dễ cập nhật: thêm luật mới chỉ cần nạp file qua giao diện, không cần huấn luyện lại
- Giao diện thân thiện, không cần kiến thức kỹ thuật để sử dụng

### 1.4. Thách thức

| Thách thức | Chi tiết |
|---|---|
| Văn bản dài | Luật TTATGT 2024: ~89 Điều; Thông tư kèm bảng biểu phụ lục |
| Cấu trúc phân cấp | Phần → Chương → Mục → Điều → Khoản → Điểm |
| Khoảng cách từ vựng | Người dùng: "chạy xe 60km/h trong phố"; Luật: "tốc độ tối đa trong khu vực đông dân cư" |
| Định dạng nguồn | PDF (text-based) và TXT |

---

## 2. Khái niệm nền tảng

### 2.0. Sơ đồ tổng quan — RAG hoạt động thế nào?

> Xem sơ đồ: **[rag-pipeline-overview.drawio](rag-pipeline-overview.drawio)**
>
> Mở bằng draw.io (tiện ích VS Code hoặc app.diagrams.net) để xem đầy đủ.

### 2.1. Vấn đề: Tại sao không cho LLM đọc toàn bộ luật?

LLM (mô hình ngôn ngữ lớn) như ChatGPT hay Gemini có giới hạn context window (số lượng ký tự xử lý được mỗi lần). Ngoài ra, LLM có thể "bịa" thông tin (hiện tượng hallucination) nếu không có nguồn cụ thể.

Vì vậy, thay vì cho LLM đọc toàn bộ văn bản, hệ thống chỉ tìm ra vài đoạn liên quan nhất rồi đưa cho LLM tổng hợp. Cách tiếp cận này gọi là **RAG**.

### 2.2. RAG là gì?

**RAG (Retrieval-Augmented Generation)** nghĩa là tìm kiếm trước, sinh câu trả lời sau.

Thay vì để LLM tự nhớ mọi thứ, hệ thống thực hiện hai giai đoạn:

1. **Tìm kiếm (Retrieval):** tìm các đoạn văn bản liên quan từ kho dữ liệu.
2. **Sinh câu trả lời (Generation):** đưa các đoạn tìm được vào LLM và yêu cầu tổng hợp câu trả lời chỉ dựa trên các đoạn đó.

Nhờ vậy, câu trả lời vừa có căn cứ, vừa biết rõ nguồn gốc.

### 2.3. Embedding là gì?

> Xem diagram minh họa: **[rag-concepts.drawio](rag-concepts.drawio)** — phần "Embedding"

Embedding là quá trình chuyển đổi một đoạn văn bản thành một **vector** (mảng số) sao cho:

- Hai đoạn văn bản có nghĩa tương tự thì vector nằm gần nhau trong không gian.
- Hai đoạn văn bản khác nghĩa thì vector nằm xa nhau.

Ví dụ, "chạy xe quá tốc độ trong phố" và "vi phạm tốc độ tối đa trong khu vực đông dân cư" sẽ có vector gần nhau vì cùng chủ đề.

Mô hình embedding (`multilingual-e5-large`) được huấn luyện sẵn trên hàng triệu cặp câu nên đã học được mối quan hệ ngữ nghĩa này. Mô hình chạy cục bộ, không cần gọi API.

### 2.4. Vector Database là gì?

Đây là cơ sở dữ liệu chuyên lưu trữ vector và cho phép tìm kiếm nhanh các vector gần nhất. Khi người dùng đặt câu hỏi, hệ thống chuyển câu hỏi thành vector, sau đó tìm trong cơ sở dữ liệu những vector gần nhất để lấy ra đúng các đoạn luật liên quan.

ChromaDB là một cơ sở dữ liệu vector đơn giản, chạy nhúng cùng chương trình Python và lưu dữ liệu trên đĩa.

### 2.5. Chunking là gì?

> Xem diagram minh họa: **[rag-concepts.drawio](rag-concepts.drawio)** — phần "Chunking"

Văn bản luật rất dài nên phải cắt nhỏ thành từng đoạn (chunk) trước khi embedding. Mỗi đoạn cần:

- Đủ ngữ nghĩa hoàn chỉnh, không cắt giữa câu.
- Không quá dài, vì embedding sẽ giảm chất lượng nếu đoạn quá dài.
- Có metadata (thuộc Điều nào, văn bản nào) để phục vụ trích dẫn.

Với luật Việt Nam, cách chia mỗi Điều thành một đoạn là lựa chọn tự nhiên, vì Điều là đơn vị pháp lý nhỏ nhất hoàn chỉnh.

### 2.6. LLM Synthesis là gì?

Sau khi tìm được các đoạn liên quan, hệ thống đưa chúng vào prompt (câu lệnh) cho LLM, chẳng hạn:

> "Đây là các điều luật liên quan [đoạn 1, 2, 3...]. Hãy trả lời câu hỏi X chỉ dựa trên nội dung này, kèm trích dẫn [n]."

LLM sẽ phân tích, tổng hợp và trả lời bằng ngôn ngữ tự nhiên, nhưng bị ràng buộc chỉ được dùng thông tin từ các đoạn đã cung cấp.

---

## 3. Cách tiếp cận chi tiết

### 3.1. Tổng quan pipeline

Hệ thống gồm 3 phần chính:

**A. Indexing (nạp dữ liệu — chạy khi thêm luật mới qua API/Admin UI)**

Mục đích: chuẩn bị kho dữ liệu để tìm kiếm nhanh sau này.

**B. Query (truy vấn — mỗi lần người dùng hỏi)**

Mục đích: tìm đúng điều luật + tổng hợp câu trả lời.

**C. Frontend (giao diện chat — người dùng tương tác trực tiếp)**

Mục đích: hiển thị câu trả lời dạng markdown, trích dẫn bấm được và nhãn độ tin cậy.

> Xem sơ đồ chi tiết: **[rag-pipeline-overview.drawio](rag-pipeline-overview.drawio)**

### 3.2. Quy trình nạp văn bản

| Bước | Tên | Đầu vào | Đầu ra | Xử lý cụ thể |
|---|---|---|---|---|
| 1 | Kiểm tra hợp lệ | Nội dung file + tên file | Kết quả kiểm tra | Kích thước ≤ 50MB; định dạng PDF hoặc TXT; từ chối nếu trùng số hiệu. |
| 2 | Đọc file | File PDF hoặc TXT | Văn bản thuần (chuỗi ký tự) | Dùng PyMuPDF đọc từng trang PDF → ghép thành text. Với TXT: đọc UTF-8. Kiểm tra: nếu PDF scan (0 ký tự) → từ chối. |
| 3 | Cắt đoạn | Văn bản thuần toàn bộ | Danh sách các đoạn (mỗi đoạn = 1 phần + thông tin kèm) | Dùng biểu thức chính quy tìm ranh giới "Điều N." → cắt. Mỗi đoạn = nội dung 1 Điều. Dự phòng: nếu không có Điều (thông tư/phụ lục) hoặc Điều quá dài (>1800 ký tự) → cắt theo kích thước ~1200 ký tự, chồng lấp 150 ký tự. |
| 4 | Chuyển thành vector | Nội dung mỗi đoạn | Vector 1024 chiều cho mỗi đoạn | Dùng model multilingual-e5-large (thêm tiền tố "passage: "). Xử lý hàng loạt. Chạy cục bộ trên CPU. |
| 5 | Lưu trữ | Vectors + text + metadata | Dữ liệu persistent trong ChromaDB | Lưu mỗi đoạn: mã định danh duy nhất, vector, nội dung gốc, thông tin kèm theo (số hiệu, tên văn bản, điều, khoản, ngày hiệu lực, cơ quan ban hành, loại văn bản). Tự động ghi đè nếu trùng mã. |

### 3.3. Quy trình trả lời câu hỏi

Khi người dùng gửi câu hỏi, hệ thống thực hiện sáu bước tuần tự.

**Bước 1 — Chuyển câu hỏi thành vector**

Câu hỏi (ví dụ "Tốc độ tối đa trong khu dân cư?") được đưa vào mô hình embedding multilingual-e5-large với tiền tố "query: " phía trước. Mô hình chuyển câu hỏi thành một mảng 1024 số thực. Vector này nằm cùng không gian toán học với các vector đoạn luật đã lưu trước đó nên có thể so sánh được.

**Bước 2 — Tìm kiếm đoạn luật liên quan**

Hệ thống lấy vector câu hỏi ở bước 1 gửi vào ChromaDB. ChromaDB tính độ tương đồng cosine giữa vector câu hỏi và toàn bộ vector đoạn luật trong cơ sở dữ liệu, rồi trả về 8 đoạn có điểm cao nhất. Mỗi đoạn kèm một điểm từ 0 đến 1 (1 là giống hoàn toàn, 0 là không liên quan). Ví dụ:

- "Điều 12 — tốc độ tối đa": 0.85
- "Điều 15 — khoảng cách an toàn": 0.62
- "Điều 40 — xử phạt": 0.45

**Bước 3 — Chặn kết quả kém**

Hệ thống kiểm tra điểm cao nhất trong 8 kết quả:

- Nếu nhỏ hơn 0.3, trả về ngay "Không tìm thấy điều khoản phù hợp" và không gọi LLM.
- Nếu nhỏ hơn 0.5, trả về "Không tìm thấy văn bản đủ liên quan" và không gọi LLM.
- Nếu đạt từ 0.5 trở lên thì tiếp tục sang bước 4.

Lý do là nếu không có đoạn nào liên quan mà vẫn gửi cho LLM thì LLM dễ bịa câu trả lời. Chặn sớm giúp tiết kiệm chi phí gọi API và tránh bịa luật.

**Bước 4 — Tổng hợp câu trả lời bằng LLM**

Hệ thống lấy tối đa 6 đoạn luật tốt nhất (mỗi đoạn cắt tối đa 2000 ký tự) và đánh số từ [1] đến [6]. Câu lệnh gửi cho LLM (Groq API) gồm câu hỏi của người dùng, 6 đoạn văn bản luật đã đánh số, và yêu cầu trả lời theo 4 mục (Phân tích, Giải pháp, Căn cứ pháp lý, Lưu ý) kèm chèn [n] sau mỗi nhận định để trích dẫn nguồn.

LLM đọc các đoạn luật rồi tổng hợp câu trả lời bằng ngôn ngữ tự nhiên, nhưng bị ràng buộc chỉ dùng thông tin từ các đoạn đó. Thời gian xử lý giới hạn 10 giây; nếu vượt quá thì hệ thống chuyển sang phương án dự phòng.

**Bước 5 — Đóng gói kết quả**

Hệ thống ghép câu trả lời markdown từ LLM với danh sách trích dẫn (mỗi trích dẫn gồm số hiệu văn bản, tên văn bản, điều, khoản, nội dung đầy đủ) và nhãn độ tin cậy:

- Điểm từ 0.8 trở lên: "cao" (xanh)
- Điểm từ 0.5 trở lên: "trung bình" (vàng)
- Điểm dưới 0.5: "thấp" (đỏ)

Kết quả được trả về dưới dạng JSON cho giao diện hiển thị.

**Bước 6 — Dự phòng khi LLM lỗi**

Nếu LLM quá thời gian, hết lượt truy cập hoặc gặp lỗi bất kỳ, hệ thống không để trống mà trả về nguyên văn các đoạn luật gốc kèm trích dẫn, để người dùng vẫn đọc được điều luật liên quan dù chưa có phần tổng hợp.

| Bước | Tên | Đầu vào | Đầu ra |
|---|---|---|---|
| 1 | Chuyển câu hỏi thành vector | Câu hỏi (text) | Vector 1024 chiều |
| 2 | Tìm kiếm vector | Vector câu hỏi, lấy 8 kết quả | 8 đoạn luật gần nhất, mỗi đoạn kèm điểm liên quan (thang 0-1, càng cao càng khớp) |
| 3 | Chặn kết quả kém | Các đoạn + điểm | Nếu đoạn tốt nhất chỉ đạt dưới 0.3 điểm: dừng ("không tìm thấy"); dưới 0.5: dừng ("chưa đủ liên quan"), không gọi LLM |
| 4 | Tổng hợp bằng LLM | Câu hỏi + tối đa 6 đoạn tốt nhất (trong 8) | Câu trả lời markdown có trích dẫn [n] |
| 5 | Đóng gói kết quả | Câu trả lời + thông tin nguồn | JSON (nội dung + trích dẫn + độ tin cậy) |
| 6 | Dự phòng | Khi LLM lỗi | Đoạn luật gốc + trích dẫn |

*Chi tiết từng bước (cách tính điểm liên quan, ngưỡng chặn, cách xây dựng prompt) xem mục 3.3 phía trên.*

### 3.4. Frontend — Giao diện Chat

| Thành phần | Chức năng |
|---|---|
| Trang Chat (chính) | Nhập câu hỏi, xem lịch sử hội thoại, hiển thị câu trả lời markdown |
| Ô nhập (ChatInput) | Giới hạn 500 ký tự; gửi bằng Enter hoặc nút |
| Tin nhắn (MessageBubble) | Hiển thị: nội dung markdown + badge độ tin cậy + danh sách trích dẫn |
| Trích dẫn (TrichDanItem) | Chip bấm được → mở overlay xem toàn văn điều luật |
| Badge độ tin cậy | Hiển thị: cao (xanh) / trung bình (vàng) / thấp (đỏ) |
| Loading indicator | Hiển thị khi đang chờ backend phản hồi |
| Trang Admin | Upload văn bản mới + xem/xóa danh sách văn bản đã nạp |
| Màn chào (WelcomeSuggestions) | Danh sách văn bản có sẵn + câu hỏi gợi ý |
| DieuOverlay | Overlay hiển thị toàn văn nội dung điều luật khi bấm trích dẫn |

### 3.5. Quyết định thiết kế

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| Đơn vị cắt đoạn | 1 Điều = 1 đoạn | Điều là đơn vị ngữ nghĩa hoàn chỉnh; dễ trích dẫn |
| Cắt dự phòng | ~1200 ký tự + chồng lấp 150 | Cho thông tư / phụ lục không có Điều; hoặc Điều quá dài (>1800) |
| Chuyển vector | Chạy cục bộ (multilingual-e5-large) | Miễn phí; hỗ trợ tiếng Việt; không phụ thuộc API |
| Cơ sở dữ liệu vector | ChromaDB nhúng cùng ứng dụng | Đơn giản; lưu trên đĩa; không cần server riêng |
| Mô hình ngôn ngữ | Groq API (llama-3.1-8b-instant hoặc openai/gpt-oss-20b) | Nhanh (~1-2 giây); miễn phí; đủ cho thử nghiệm |
| Ngưỡng chặn 2 mức | 0.3 (không tìm thấy) / 0.5 (chưa đủ) | Không gọi LLM khi thiếu dữ liệu → tiết kiệm + tránh bịa |
| Độ tin cậy 3 mức | ≥0.8 cao / ≥0.5 trung bình / <0.5 thấp | Cho người dùng biết nên tin kết quả đến đâu |
| Dự phòng | Trả nguyên văn đoạn luật khi LLM lỗi | Đảm bảo luôn có kết quả dù LLM gặp sự cố |
| Tên bộ sưu tập | `luat_giao_thong` | Phân biệt phạm vi, chỉ chứa luật giao thông |
| Giao diện | React 19 + Vite + Tailwind v4 | Nhanh, hiện đại, chia theo thành phần, CSS tiện lợi |
| Hiển thị markdown | react-markdown | Hỗ trợ [n] trích dẫn bấm được trong nội dung |

---

## 4. Công nghệ sử dụng

### 4.1. Kiến trúc tổng quan

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| Giao diện | React 19 + Vite + TypeScript + Tailwind v4 | Ứng dụng chat; hiển thị markdown và trích dẫn |
| Máy chủ | Python 3.11+ / FastAPI | API bất đồng bộ; kiểm tra dữ liệu tự động |
| CSDL vector | ChromaDB (lưu trên đĩa) | Lưu trữ + tìm kiếm vector; chỉ mục cosine |
| Nhúng vector | sentence-transformers (HuggingFace) | Chuyển text → vector 1024 chiều; chạy cục bộ |
| LLM tổng hợp | Groq API (openai/gpt-oss-20b) | Tổng hợp câu trả lời; miễn phí |
| Đọc PDF | PyMuPDF (fitz) | Trích xuất text từ PDF; phát hiện scan |
| Cấu hình | pydantic-settings + .env | Tách biệt tham số; không sửa code khi đổi model |

### 4.2. Yêu cầu phần cứng

- RAM: ≥ 4GB (model embedding ~2GB + ứng dụng)
- GPU: không bắt buộc (embedding chạy CPU; LLM qua API)
- Ổ đĩa: ~3GB (bộ nhớ đệm model + dữ liệu ChromaDB)

### 4.3. Mô hình Embedding

| Thuộc tính | Giá trị |
|---|---|
| Model | intfloat/multilingual-e5-large |
| Số chiều | 1024 (mỗi text → mảng 1024 số thực) |
| Kích thước | ~2.2 GB (tải 1 lần, lưu đệm cục bộ) |
| Ngôn ngữ | 100+ ngôn ngữ, bao gồm tiếng Việt |
| Cách dùng | Tiền tố "query: " cho câu hỏi, "passage: " cho tài liệu |

### 4.4. Nhà cung cấp LLM

| Nhà cung cấp | Model | Gói miễn phí | Độ trễ | Vai trò |
|---|---|---|---|---|
| Groq | openai/gpt-oss-20b | 30 lượt/phút | ~1-2 giây | Tổng hợp câu trả lời |

---

## 5. Dữ liệu nguồn

### 5.1. Văn bản luật giao thông (seed data)

| File | Văn bản | Ghi chú |
|---|---|---|
| `36_2024_QH15_444251.pdf` | Luật Trật tự, An toàn giao thông đường bộ 2024 | Luật chính, nhiều Điều |
| `35_2024_QH15_588811.pdf` | Luật 35/2024/QH15 | Luật liên quan giao thông |
| `38_2024_TT-BGTVT_622477.pdf` | Thông tư 38/2024/TT-BGTVT | Thông tư hướng dẫn; có phụ lục/bảng biểu |

### 5.2. Cách nạp

Nạp qua Admin UI (upload form) hoặc API `POST /api/documents` với thông tin kèm theo gồm: số hiệu, tên văn bản, ngày ban hành, ngày hiệu lực, cơ quan ban hành, loại văn bản.

---

## 6. Thư viện sử dụng

### 6.1. Backend — Python

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| fastapi | ≥ 0.104 | Web framework, API bất đồng bộ |
| uvicorn[standard] | ≥ 0.24 | Máy chủ chạy FastAPI |
| pydantic-settings | ≥ 2.1 | Đọc cấu hình từ .env |
| chromadb | ≥ 0.4.18 | Cơ sở dữ liệu vector |
| sentence-transformers | ≥ 2.2 | Chạy mô hình nhúng vector |
| pymupdf | ≥ 1.23 | Đọc PDF → văn bản thuần |
| groq | ≥ 0.4 | Gọi Groq LLM API |
| google-generativeai | ≥ 0.3 | Gọi Gemini API |
| python-multipart | ≥ 0.0.6 | Xử lý upload file |
| httpx | ≥ 0.25 | HTTP client |

### 6.2. Frontend — Node.js

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| react | ^19.2.8 | Thư viện giao diện |
| vite | ^8.2.0 | Công cụ build + dev server |
| typescript | ~6.0.2 | Kiểm tra kiểu dữ liệu |
| tailwindcss | ^4.3.3 | CSS tiện ích |
| axios | ^1.19.0 | Gọi API backend |
| react-router-dom | ^7.18.2 | Điều hướng trang |
| react-markdown | ^10.1.0 | Hiển thị markdown và trích dẫn |

### 6.3. Vai trò từng thư viện trong pipeline

**Nạp văn bản (Indexing):**
- `pymupdf` → đọc PDF ra văn bản thuần
- Python `re` → cắt text thành chunk theo ranh giới Điều
- `sentence-transformers` → nhúng chunk → vector 1024 chiều
- `chromadb` → lưu (id, vector, text, metadata) vào đĩa

**Truy vấn (Query):**
- `sentence-transformers` → nhúng câu hỏi → vector
- `chromadb` → tìm kiếm cosine top-k chunk gần nhất
- `groq` → gửi prompt (câu hỏi + chunks) → nhận câu trả lời
- `fastapi` → API endpoint nhận request / trả response

**Giao diện (Frontend):**
- `react` + `vite` → ứng dụng build nhanh
- `axios` → gọi POST /api/query, upload documents
- `react-markdown` → hiển thị câu trả lời (markdown + [n] trích dẫn bấm được)
- `tailwindcss` → giao diện responsive, thân thiện di động

---

## 7. API Endpoints (Phase 1)

| Phương thức | Đường dẫn | Mô tả | Xác thực |
|---|---|---|---|
| POST | `/api/query` | Hỏi đáp luật giao thông | Công khai |
| POST | `/api/documents` | Upload văn bản mới | Không (Phase 1) |
| GET | `/api/documents?page&page_size` | Liệt kê văn bản đã nạp | Không |
| DELETE | `/api/documents/{soHieu}` | Xóa văn bản theo số hiệu | Không (Phase 1) |

### 7.1. Cấu trúc phản hồi chính

```json
{
  "noiDung": "Câu trả lời dạng markdown có [1] trích dẫn...",
  "trichDan": [
    {
      "soHieu": "36/2024/QH15",
      "tenVanBan": "Luật TTATGT đường bộ 2024",
      "dieu": "Điều 12",
      "khoan": "3",
      "noiDungDayDu": "Nội dung nguyên văn đoạn luật..."
    }
  ],
  "doTinCay": "cao",
  "chunksGoc": null
}
```

Giải thích các trường:
- **noiDung** — nội dung câu trả lời (định dạng markdown, có chèn [n] để trích dẫn)
- **trichDan** — danh sách các nguồn trích dẫn (số hiệu, tên văn bản, điều, khoản, nội dung đầy đủ)
- **doTinCay** — mức độ tin cậy: "cao" / "trung bình" / "thấp"
- **chunksGoc** — chỉ có khi LLM lỗi: trả nguyên văn đoạn luật gốc

---

## 8. Cấu trúc source code

```
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app, khởi tạo, CORS, middleware log
│   │   ├── config.py                # Cấu hình (pydantic-settings, .env)
│   │   ├── logging_config.py        # Logger tập trung (console + file)
│   │   ├── api/
│   │   │   ├── dependencies.py      # Quản lý phụ thuộc (get/set pipeline, store)
│   │   │   └── routes/
│   │   │       ├── query.py         # POST /api/query
│   │   │       └── documents.py     # POST/GET/DELETE /api/documents
│   │   ├── chunking/
│   │   │   └── chunker.py           # VietnameseLawChunker (cắt theo Điều + fallback)
│   │   ├── models/
│   │   │   └── schemas.py           # Pydantic: QueryRequest, KetQuaTraLoi, TrichDan
│   │   ├── pipelines/
│   │   │   ├── document_pipeline.py # parse → chunk → embed → store
│   │   │   └── query_pipeline.py    # embed → search → gate → synthesis → response
│   │   ├── prompts/
│   │   │   └── system_prompts.py    # SYNTHESIS_SYSTEM_PROMPT
│   │   ├── providers/
│   │   │   ├── llm_provider.py      # Giao diện LLM chung
│   │   │   ├── embedding_provider.py # Giao diện Embedding chung
│   │   │   ├── groq_provider.py     # Groq implementation
│   │   │   ├── gemini_provider.py   # Gemini implementation (chưa sử dụng)
│   │   │   └── huggingface_embedding.py # Nhúng vector bằng sentence-transformers
│   │   └── storage/
│   │       └── vector_store.py      # ChromaDB wrapper (search, add, delete, list)
│   ├── data/chroma/                 # ChromaDB persistent storage
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Router: / → ChatPage, /admin → AdminPage
│   │   ├── api/client.ts            # Gọi API, cấu hình địa chỉ backend
│   │   ├── hooks/
│   │   │   ├── useQuery.ts          # Gọi /api/query, quản lý lịch sử chat
│   │   │   └── useDocuments.ts      # Upload / list / delete documents
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx         # Trang chat chính
│   │   │   └── AdminPage.tsx        # Upload + quản lý văn bản
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatInput.tsx    # Ô nhập câu hỏi (500 ký tự)
│   │   │   │   ├── MessageList.tsx  # Danh sách tin nhắn
│   │   │   │   ├── MessageBubble.tsx # Hiển thị 1 tin: markdown + badge + citations
│   │   │   │   ├── TrichDanItem.tsx # Chip trích dẫn bấm được
│   │   │   │   └── WelcomeSuggestions.tsx # Màn chào + gợi ý
│   │   │   └── common/
│   │   │       ├── AppLayout.tsx    # Bố cục chung + điều hướng
│   │   │       ├── ConfidenceBadge.tsx  # Badge cao/TB/thấp
│   │   │       ├── DieuOverlay.tsx  # Overlay xem toàn văn Điều
│   │   │       └── LoadingIndicator.tsx # Spinner chờ phản hồi
│   │   └── types/index.ts          # TrichDan, KetQuaTraLoi, Message, DocumentMetadata
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
│
└── data/seed/                       # File PDF luật gốc
```

---

## 9. Kết luận tính khả thi Phase 1

| Khía cạnh | Đánh giá | Ghi chú |
|---|---|---|
| Kỹ thuật | Khả thi cao | Thư viện ổn định, cộng đồng lớn; RAG là mô hình đã chứng minh hiệu quả |
| Thời gian | 2-3 tuần (1 người) | Backend + Frontend + kiểm thử cơ bản |
| Chất lượng | Đủ cho thử nghiệm | Tìm kiếm vector cơ bản; đúng với câu hỏi giao thông đơn giản |
| Mở rộng | Dễ | Thêm luật chỉ cần upload file; đổi LLM chỉ cần đổi .env |
| Trải nghiệm | Tốt | Chat UI trực quan, trích dẫn bấm được, badge tin cậy |

### 9.1. Hạn chế Phase 1

| Hạn chế | Ảnh hưởng |
|---|---|
| Chỉ tìm kiếm theo vector (cosine) | Yếu với tìm chính xác (số Điều, số hiệu văn bản) |
| Khoảng cách từ vựng | "chạy nhanh" khó khớp "vượt quá tốc độ" |
| Chưa có xác minh chéo | Không biết LLM tổng hợp đúng/sai so với văn bản gốc |
| Không có xác thực | Ai cũng upload/xóa văn bản được |

---

## 10. Chạy ứng dụng

```bash
# Backend
cd backend
copy .env.example .env   # điền API key
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Windows: dùng `python -m uvicorn`, `python -m pip` (tránh .exe bị Application Control chặn).
