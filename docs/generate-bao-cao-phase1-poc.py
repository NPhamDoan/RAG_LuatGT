"""Generate bao-cao-phase1-poc.docx từ nội dung Phase 1 POC."""
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from pathlib import Path

doc = Document()

# --- Page margins ---
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

# --- Style setup ---
style = doc.styles["Normal"]
style.font.name = "Times New Roman"
style.font.size = Pt(12)


def set_cell_shading(cell, color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shading = tcPr.makeelement(qn("w:shd"), {
        qn("w:fill"): color, qn("w:val"): "clear", qn("w:color"): "auto",
    })
    tcPr.append(shading)


def add_table(headers, rows):
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.style = "Table Grid"
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        cell = tbl.rows[0].cells[i]
        cell.text = ""
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.size = Pt(11)
        run.font.name = "Times New Roman"
        set_cell_shading(cell, "D9E2F3")
    for r_idx, row_data in enumerate(rows):
        for c_idx, val in enumerate(row_data):
            cell = tbl.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            run = cell.paragraphs[0].add_run(val)
            run.font.size = Pt(11)
            run.font.name = "Times New Roman"
    doc.add_paragraph()


def h1(text):
    doc.add_heading(text, level=1)


def h2(text):
    doc.add_heading(text, level=2)


def p(text):
    doc.add_paragraph(text)


def bold_p(text):
    para = doc.add_paragraph()
    para.add_run(text).bold = True


def bullet(text):
    doc.add_paragraph(text, style="List Bullet")


def mixed(parts):
    para = doc.add_paragraph()
    for text, bold in parts:
        run = para.add_run(text)
        run.bold = bold


# ============================================================
# TITLE
# ============================================================
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("BÁO CÁO ĐIỀU TRA TÍNH KHẢ THI")
run.bold = True
run.font.size = Pt(18)

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = subtitle.add_run("PHASE 1: Core RAG Pipeline + Chat UI")
run.bold = True
run.font.size = Pt(14)

sub2 = doc.add_paragraph()
sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = sub2.add_run("Hệ thống RAG Tra cứu Luật Giao Thông Việt Nam")
run.italic = True
run.font.size = Pt(12)

doc.add_paragraph()

# ============================================================
# 1. BÀI TOÁN
# ============================================================
h1("1. Bài toán")

h2("1.1. Mô tả bài toán")
p("Xây dựng hệ thống cho phép người dùng (không chuyên luật) mô tả tình huống giao thông "
  "thực tế bằng tiếng Việt, hệ thống tự động tìm đúng điều luật liên quan rồi tổng hợp "
  "câu trả lời có căn cứ pháp lý kèm trích dẫn nguồn cụ thể. Giao diện chat trực quan, "
  "dễ sử dụng.")

h2("1.2. Đầu vào / Đầu ra")
mixed([("Đầu vào: ", True), ("Câu hỏi / mô tả tình huống giao thông bằng tiếng Việt.", False)])
mixed([("Đầu ra: ", True), ("Câu trả lời tổng hợp + trích dẫn (số hiệu, Điều, Khoản) + "
        "chỉ số độ tin cậy + hiển thị trên giao diện chat.", False)])

h2("1.3. Ràng buộc")
bullet("Bám sát văn bản — CHỈ dùng văn bản luật thật, KHÔNG bịa nội dung")
bullet("Hỗ trợ tiếng Việt: thuật ngữ pháp lý lẫn đời thường")
bullet("Trích dẫn nguồn rõ ràng (số hiệu, Điều, Khoản)")
bullet("Thời gian phản hồi < 5 giây")
bullet("Dễ cập nhật: thêm luật mới chỉ cần nạp file, không cần huấn luyện lại")
bullet("Giao diện thân thiện, không cần kiến thức kỹ thuật để sử dụng")

h2("1.4. Thách thức")
add_table(
    ["Thách thức", "Chi tiết"],
    [
        ["Văn bản dài", "Luật TTATGT 2024: ~89 Điều; Thông tư kèm bảng biểu phụ lục"],
        ["Cấu trúc phân cấp", "Phần → Chương → Mục → Điều → Khoản → Điểm"],
        ["Khoảng cách từ vựng", "Người dùng: \"chạy xe 60km/h trong phố\"; "
         "Luật: \"tốc độ tối đa trong khu vực đông dân cư\""],
        ["Định dạng nguồn", "PDF (text-based) và TXT"],
    ],
)

# ============================================================
# 2. KHÁI NIỆM NỀN TẢNG
# ============================================================
h1("2. Khái niệm nền tảng")

h2("2.1. Vấn đề: Tại sao không cho LLM đọc toàn bộ luật?")
p("LLM (mô hình ngôn ngữ lớn) có giới hạn context window (số ký tự đọc được mỗi lần). "
  "Ngoài ra LLM có thể \"bịa\" thông tin nếu không có nguồn cụ thể.")
bold_p("Giải pháp: KHÔNG cho LLM đọc hết, mà chỉ TÌM ĐÚNG vài đoạn liên quan rồi đưa "
       "cho LLM tổng hợp. Cách tiếp cận này gọi là RAG.")

h2("2.2. RAG là gì?")
p("RAG (Retrieval-Augmented Generation) nghĩa là: Tìm kiếm trước, sinh câu trả lời sau.")
p("Thay vì LLM tự nhớ mọi thứ, hệ thống sẽ:")
bullet("TÌM KIẾM (Retrieval) — tìm đoạn văn bản liên quan từ kho dữ liệu")
bullet("SINH (Generation) — đưa đoạn tìm được vào LLM, yêu cầu tổng hợp câu trả lời "
       "CHỈ dựa trên đoạn đó")
p("Kết quả: câu trả lời có căn cứ, biết rõ nguồn từ đâu.")

h2("2.3. Embedding là gì?")
p("Embedding là quá trình chuyển đổi một đoạn text thành một VECTOR (mảng số) sao cho:")
bullet("Hai đoạn text CÓ NGHĨA TƯƠNG TỰ → vector GẦN NHAU trong không gian")
bullet("Hai đoạn text KHÁC NGHĨA → vector XA NHAU")
p("Ví dụ: \"chạy xe quá tốc độ trong phố\" và \"vi phạm tốc độ tối đa trong khu vực đông "
  "dân cư\" sẽ có vector gần nhau vì cùng chủ đề.")
p("Model embedding (multilingual-e5-large) được huấn luyện sẵn trên hàng triệu cặp câu. "
  "Chạy cục bộ, không cần API.")

h2("2.4. Vector Database là gì?")
p("Cơ sở dữ liệu chuyên lưu trữ vector và cho phép TÌM KIẾM NHANH các vector gần nhất. "
  "Khi người dùng hỏi:")
bullet("Embed câu hỏi → vector Q")
bullet("Tìm trong DB các vector gần Q nhất (cosine similarity) → ra đúng đoạn luật liên quan")
p("ChromaDB là một vector DB đơn giản, chạy nhúng cùng process Python, lưu trên đĩa.")

h2("2.5. Chunking là gì?")
p("Văn bản luật rất dài → phải CẮT NHỎ thành từng đoạn (chunk) trước khi embed. "
  "Mỗi chunk cần:")
bullet("Đủ ngữ nghĩa hoàn chỉnh (không cắt giữa câu)")
bullet("Không quá dài (embedding mất chất lượng nếu text quá dài)")
bullet("Có metadata (thuộc Điều nào, văn bản nào) để trích dẫn")
p("Với luật Việt Nam: 1 Điều = 1 chunk là lựa chọn tự nhiên (Điều là đơn vị pháp lý "
  "nhỏ nhất hoàn chỉnh).")

h2("2.6. LLM Synthesis là gì?")
p("Sau khi tìm được các chunk liên quan, đưa chúng vào prompt cho LLM:")
p("\"Đây là các điều luật liên quan [chunk 1, 2, 3...]. Hãy trả lời câu hỏi X CHỈ dựa "
  "trên nội dung này, kèm trích dẫn [n].\"")
p("LLM sẽ tổng hợp, phân tích, và trả lời bằng ngôn ngữ tự nhiên — nhưng bị ràng buộc "
  "chỉ dùng thông tin từ chunk.")

# ============================================================
# 3. CÁCH TIẾP CẬN CHI TIẾT
# ============================================================
h1("3. Cách tiếp cận chi tiết")

h2("3.1. Tổng quan pipeline")
p("Hệ thống gồm 3 phần chính:")
bold_p("A. Indexing (nạp dữ liệu — chạy khi thêm luật mới)")
p("Mục đích: chuẩn bị kho dữ liệu để tìm kiếm nhanh sau này.")
bold_p("B. Query (truy vấn — mỗi lần người dùng hỏi)")
p("Mục đích: tìm đúng điều luật + tổng hợp câu trả lời.")
bold_p("C. Frontend (giao diện chat)")
p("Mục đích: hiển thị câu trả lời dạng markdown, trích dẫn bấm được và nhãn độ tin cậy.")

h2("3.2. Quy trình nạp văn bản")
add_table(
    ["Bước", "Tên", "Xử lý cụ thể"],
    [
        ["1", "Kiểm tra hợp lệ", "Kích thước ≤ 50MB; định dạng PDF/TXT; từ chối nếu trùng số hiệu"],
        ["2", "Đọc file", "PyMuPDF đọc PDF → ghép text. TXT: đọc UTF-8. PDF scan (0 ký tự) → từ chối"],
        ["3", "Cắt đoạn", "Regex tìm ranh giới \"Điều N.\" → cắt. Dự phòng: ~1200 ký tự, chồng lấp 150"],
        ["4", "Chuyển vector", "multilingual-e5-large (tiền tố \"passage: \"). Xử lý hàng loạt. Chạy CPU"],
        ["5", "Lưu trữ", "ChromaDB: id + vector + text + metadata (số hiệu, tên, điều, khoản, ngày...). Tự động ghi đè nếu trùng"],
    ],
)

h2("3.3. Quy trình trả lời câu hỏi")
p("Khi người dùng gửi câu hỏi, hệ thống thực hiện sáu bước tuần tự.")

bold_p("Bước 1 — Chuyển câu hỏi thành vector")
p("Câu hỏi (ví dụ \"Tốc độ tối đa trong khu dân cư?\") được đưa vào mô hình embedding "
  "multilingual-e5-large với tiền tố \"query: \" phía trước. Mô hình chuyển câu hỏi thành "
  "một mảng 1024 số thực. Vector này nằm cùng không gian toán học với các vector đoạn luật "
  "đã lưu trước đó nên có thể so sánh được.")

bold_p("Bước 2 — Tìm kiếm đoạn luật liên quan")
p("Hệ thống lấy vector câu hỏi ở bước 1 gửi vào ChromaDB. ChromaDB tính độ tương đồng cosine "
  "giữa vector câu hỏi và toàn bộ vector đoạn luật trong cơ sở dữ liệu, rồi trả về 8 đoạn có "
  "điểm cao nhất. Mỗi đoạn kèm một điểm từ 0 đến 1 (1 là giống hoàn toàn, 0 là không liên quan). "
  "Ví dụ:")
bullet("\"Điều 12 — tốc độ tối đa\": 0.85")
bullet("\"Điều 15 — khoảng cách an toàn\": 0.62")
bullet("\"Điều 40 — xử phạt\": 0.45")

bold_p("Bước 3 — Chặn kết quả kém")
p("Hệ thống kiểm tra điểm cao nhất trong 8 kết quả:")
bullet("Nếu nhỏ hơn 0.3, trả về ngay \"Không tìm thấy điều khoản phù hợp\" và không gọi LLM.")
bullet("Nếu nhỏ hơn 0.5, trả về \"Không tìm thấy văn bản đủ liên quan\" và không gọi LLM.")
bullet("Nếu đạt từ 0.5 trở lên thì tiếp tục sang bước 4.")
p("Lý do là nếu không có đoạn nào liên quan mà vẫn gửi cho LLM thì LLM dễ bịa câu trả lời. "
  "Chặn sớm giúp tiết kiệm chi phí gọi API và tránh bịa luật.")

bold_p("Bước 4 — Tổng hợp câu trả lời bằng LLM")
p("Hệ thống lấy tối đa 6 đoạn luật tốt nhất (mỗi đoạn cắt tối đa 2000 ký tự) và đánh số "
  "từ [1] đến [6]. Câu lệnh gửi cho LLM (Groq API) gồm câu hỏi của người dùng, 6 đoạn văn "
  "bản luật đã đánh số, và yêu cầu trả lời theo 4 mục (Phân tích, Giải pháp, Căn cứ pháp lý, "
  "Lưu ý) kèm chèn [n] sau mỗi nhận định để trích dẫn nguồn.")
p("LLM đọc các đoạn luật rồi tổng hợp câu trả lời bằng ngôn ngữ tự nhiên, nhưng bị ràng buộc "
  "chỉ dùng thông tin từ các đoạn đó. Thời gian xử lý giới hạn 10 giây; nếu vượt quá thì hệ "
  "thống chuyển sang phương án dự phòng.")

bold_p("Bước 5 — Đóng gói kết quả")
p("Hệ thống ghép câu trả lời markdown từ LLM với danh sách trích dẫn (mỗi trích dẫn gồm số "
  "hiệu văn bản, tên văn bản, điều, khoản, nội dung đầy đủ) và nhãn độ tin cậy:")
bullet("Điểm từ 0.8 trở lên: \"cao\" (xanh)")
bullet("Điểm từ 0.5 trở lên: \"trung bình\" (vàng)")
bullet("Điểm dưới 0.5: \"thấp\" (đỏ)")
p("Kết quả được trả về dưới dạng JSON cho giao diện hiển thị.")

bold_p("Bước 6 — Dự phòng khi LLM lỗi")
p("Nếu LLM quá thời gian, hết lượt truy cập hoặc gặp lỗi bất kỳ, hệ thống không để trống mà "
  "trả về nguyên văn các đoạn luật gốc kèm trích dẫn, để người dùng vẫn đọc được điều luật "
  "liên quan dù chưa có phần tổng hợp.")

bold_p("Bảng tóm tắt:")
add_table(
    ["Bước", "Tên", "Đầu vào → Đầu ra"],
    [
        ["1", "Chuyển câu hỏi thành vector", "Text → vector 1024 chiều (tiền tố \"query: \")"],
        ["2", "Tìm kiếm đoạn luật", "So sánh vector câu hỏi với tất cả vector đoạn luật trong CSDL → lấy 8 đoạn giống nhất. Mỗi đoạn có điểm liên quan (0-1, càng cao càng khớp về nghĩa)"],
        ["3", "Chặn kết quả kém", "Nếu đoạn tốt nhất chỉ đạt dưới 0.3 điểm: \"không tìm thấy\"; dưới 0.5: \"chưa đủ liên quan\". Dừng, không gọi LLM"],
        ["4", "Tổng hợp bằng LLM", "Câu hỏi + tối đa 6 đoạn tốt nhất (trong 8) → câu trả lời markdown có [n] trích dẫn"],
        ["5", "Đóng gói kết quả", "Markdown + trích dẫn + độ tin cậy (≥0.8 cao / ≥0.5 TB / <0.5 thấp)"],
        ["6", "Dự phòng", "LLM lỗi → trả nguyên văn đoạn luật gốc + trích dẫn"],
    ],
)

h2("3.4. Giao diện Chat")
add_table(
    ["Thành phần", "Chức năng"],
    [
        ["Trang Chat (chính)", "Nhập câu hỏi, xem lịch sử, hiển thị câu trả lời markdown"],
        ["Ô nhập (ChatInput)", "Giới hạn 500 ký tự; gửi bằng Enter hoặc nút"],
        ["Tin nhắn (MessageBubble)", "Nội dung markdown + badge độ tin cậy + danh sách trích dẫn"],
        ["Trích dẫn (TrichDanItem)", "Chip bấm được → mở overlay xem toàn văn điều luật"],
        ["Badge độ tin cậy", "Cao (xanh) / trung bình (vàng) / thấp (đỏ)"],
        ["Loading indicator", "Spinner khi đang chờ backend phản hồi"],
        ["Trang Admin", "Upload văn bản + xem/xóa danh sách văn bản đã nạp"],
        ["Màn chào", "Danh sách văn bản có sẵn + câu hỏi gợi ý"],
    ],
)

h2("3.5. Quyết định thiết kế")
add_table(
    ["Quyết định", "Lựa chọn", "Lý do"],
    [
        ["Đơn vị cắt đoạn", "1 Điều = 1 đoạn", "Điều là đơn vị ngữ nghĩa hoàn chỉnh; dễ trích dẫn"],
        ["Cắt dự phòng", "~1200 ký tự + chồng lấp 150", "Cho thông tư/phụ lục; hoặc Điều quá dài (>1800)"],
        ["Nhúng vector", "Chạy cục bộ (multilingual-e5-large)", "Miễn phí; hỗ trợ tiếng Việt; không phụ thuộc API"],
        ["CSDL vector", "ChromaDB nhúng cùng ứng dụng", "Đơn giản; lưu trên đĩa; không cần server riêng"],
        ["Mô hình ngôn ngữ", "Groq API (openai/gpt-oss-20b)", "Nhanh (~1-2 giây); miễn phí; đủ cho thử nghiệm"],
        ["Ngưỡng chặn 2 mức", "0.3 / 0.5", "Không gọi LLM khi thiếu dữ liệu → tiết kiệm + tránh bịa"],
        ["Dự phòng", "Trả nguyên văn đoạn luật", "Đảm bảo luôn có kết quả dù LLM gặp sự cố"],
        ["Giao diện", "React 19 + Vite + Tailwind v4", "Nhanh, hiện đại, CSS tiện lợi"],
    ],
)

# ============================================================
# 4. CÔNG NGHỆ SỬ DỤNG
# ============================================================
h1("4. Công nghệ sử dụng")

h2("4.1. Kiến trúc tổng quan")
add_table(
    ["Tầng", "Công nghệ", "Vai trò"],
    [
        ["Giao diện", "React 19 + Vite + TypeScript + Tailwind v4", "Ứng dụng chat; hiển thị markdown và trích dẫn"],
        ["Máy chủ", "Python 3.11+ / FastAPI", "API bất đồng bộ; kiểm tra dữ liệu tự động"],
        ["CSDL vector", "ChromaDB (lưu trên đĩa)", "Lưu trữ + tìm kiếm vector; chỉ mục cosine"],
        ["Nhúng vector", "sentence-transformers", "Chuyển text → vector 1024 chiều; chạy cục bộ"],
        ["LLM tổng hợp", "Groq API (openai/gpt-oss-20b)", "Tổng hợp câu trả lời; miễn phí"],
        ["Đọc PDF", "PyMuPDF (fitz)", "Trích xuất text; phát hiện scan"],
        ["Cấu hình", "pydantic-settings + .env", "Tách biệt tham số ra file cấu hình"],
    ],
)

h2("4.2. Yêu cầu phần cứng")
add_table(
    ["Tài nguyên", "Yêu cầu tối thiểu", "Ghi chú"],
    [
        ["RAM", "≥ 4 GB", "Mô hình nhúng ~2GB + ứng dụng"],
        ["GPU", "Không bắt buộc", "Nhúng vector chạy CPU; LLM qua API"],
        ["Ổ đĩa", "~3 GB", "Bộ nhớ đệm mô hình + dữ liệu ChromaDB"],
    ],
)

h2("4.3. Mô hình Embedding")
add_table(
    ["Thuộc tính", "Giá trị"],
    [
        ["Model", "intfloat/multilingual-e5-large"],
        ["Số chiều", "1024"],
        ["Kích thước", "~2.2 GB (tải 1 lần, lưu đệm cục bộ)"],
        ["Ngôn ngữ", "100+ ngôn ngữ, bao gồm tiếng Việt"],
        ["Cách dùng", "Tiền tố \"query: \" cho câu hỏi, \"passage: \" cho tài liệu"],
    ],
)

h2("4.4. Thư viện Backend (Python)")
add_table(
    ["Thư viện", "Phiên bản", "Mục đích"],
    [
        ["fastapi", "≥ 0.104", "Web framework, API"],
        ["uvicorn[standard]", "≥ 0.24", "Máy chủ chạy FastAPI"],
        ["pydantic-settings", "≥ 2.1", "Đọc cấu hình .env"],
        ["chromadb", "≥ 0.4.18", "Cơ sở dữ liệu vector"],
        ["sentence-transformers", "≥ 2.2", "Mô hình nhúng vector"],
        ["pymupdf", "≥ 1.23", "Đọc file PDF"],
        ["groq", "≥ 0.4", "Gọi Groq LLM API"],
        ["google-generativeai", "≥ 0.3", "Gọi Gemini API"],
        ["python-multipart", "≥ 0.0.6", "Xử lý upload file"],
        ["httpx", "≥ 0.25", "HTTP client"],
    ],
)

h2("4.5. Thư viện Frontend (Node.js)")
add_table(
    ["Thư viện", "Phiên bản", "Mục đích"],
    [
        ["react", "^19.2.8", "Thư viện giao diện"],
        ["vite", "^8.2.0", "Công cụ build + dev server"],
        ["typescript", "~6.0.2", "Kiểm tra kiểu dữ liệu"],
        ["tailwindcss", "^4.3.3", "CSS tiện ích"],
        ["axios", "^1.19.0", "Gọi API backend"],
        ["react-router-dom", "^7.18.2", "Điều hướng trang"],
        ["react-markdown", "^10.1.0", "Hiển thị markdown và trích dẫn"],
    ],
)

# ============================================================
# 5. DỮ LIỆU NGUỒN
# ============================================================
h1("5. Dữ liệu nguồn")

add_table(
    ["File", "Văn bản", "Ghi chú"],
    [
        ["36_2024_QH15_444251.pdf", "Luật Trật tự, An toàn giao thông đường bộ 2024", "Luật chính, nhiều Điều"],
        ["35_2024_QH15_588811.pdf", "Luật 35/2024/QH15", "Luật liên quan giao thông"],
        ["38_2024_TT-BGTVT_622477.pdf", "Thông tư 38/2024/TT-BGTVT", "Thông tư hướng dẫn; có phụ lục"],
    ],
)
p("Nạp qua Admin UI (upload form) hoặc API POST /api/documents (multipart) với metadata: "
  "số hiệu, tên văn bản, ngày ban hành, ngày hiệu lực, cơ quan ban hành, loại văn bản.")

# ============================================================
# 6. API
# ============================================================
h1("6. API Endpoints")

add_table(
    ["Phương thức", "Đường dẫn", "Mô tả"],
    [
        ["POST", "/api/query", "Hỏi đáp luật giao thông (công khai)"],
        ["POST", "/api/documents", "Upload văn bản mới"],
        ["GET", "/api/documents?page&page_size", "Liệt kê văn bản đã nạp"],
        ["DELETE", "/api/documents/{soHieu}", "Xóa văn bản theo số hiệu"],
    ],
)

h2("6.1. Cấu trúc phản hồi truy vấn")
p("Các trường chính trong kết quả trả về:")
bullet("noiDung — câu trả lời markdown, có chèn [n] trích dẫn")
bullet("trichDan — danh sách nguồn (số hiệu, tên văn bản, điều, khoản, nội dung đầy đủ)")
bullet("doTinCay — mức tin cậy: \"cao\" / \"trung bình\" / \"thấp\"")
bullet("chunksGoc — chỉ có khi LLM lỗi: nguyên văn đoạn luật gốc")

# ============================================================
# 7. KẾT LUẬN
# ============================================================
h1("7. Kết luận tính khả thi Phase 1")

add_table(
    ["Khía cạnh", "Đánh giá", "Ghi chú"],
    [
        ["Kỹ thuật", "Khả thi cao", "Thư viện ổn định, cộng đồng lớn; RAG đã chứng minh hiệu quả"],
        ["Thời gian", "2-3 tuần (1 người)", "Backend + Frontend + kiểm thử cơ bản"],
        ["Chất lượng", "Đủ cho thử nghiệm", "Tìm kiếm vector cơ bản; đúng với câu hỏi đơn giản"],
        ["Mở rộng", "Dễ", "Thêm luật chỉ cần upload; đổi LLM chỉ cần đổi .env"],
        ["Trải nghiệm", "Tốt", "Chat trực quan, trích dẫn bấm được, badge tin cậy"],
    ],
)

h2("7.1. Hạn chế Phase 1")
add_table(
    ["Hạn chế", "Ảnh hưởng"],
    [
        ["Chỉ tìm kiếm theo vector (cosine)", "Yếu với tìm chính xác (số Điều, số hiệu)"],
        ["Khoảng cách từ vựng", "\"chạy nhanh\" khó khớp \"vượt quá tốc độ\""],
        ["Chưa có xác minh chéo", "Không biết LLM tổng hợp đúng/sai so với văn bản gốc"],
        ["Không có xác thực", "Ai cũng upload/xóa văn bản được"],
    ],
)

# Footer
doc.add_paragraph()
para = doc.add_paragraph()
para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run = para.add_run("Ngày lập: Tháng 8/2026")
run.italic = True

# --- Save ---
out = Path(__file__).parent / "bao-cao-phase1-poc.docx"
doc.save(str(out))
print(f"OK: {out}")
