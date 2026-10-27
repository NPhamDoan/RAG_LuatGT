"""Pydantic schemas cho API request/response."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class DocumentMetadataInput(BaseModel):
    """Metadata khi upload văn bản."""
    soHieu: str = Field(..., description="Số hiệu văn bản, vd: 36/2024/QH15")
    tenVanBan: str = Field(..., description="Tên văn bản")
    ngayBanHanh: date = Field(..., description="Ngày ban hành")
    ngayHieuLuc: date = Field(..., description="Ngày hiệu lực")
    coQuanBanHanh: str = Field(default="", description="Cơ quan ban hành")
    loaiVanBan: str = Field(default="", description="Loại: Luật, Thông tư, Nghị định...")


class DocumentUpdateInput(BaseModel):
    """Metadata cho phép sửa (chỉ gửi trường muốn đổi; không đụng text/vector)."""
    soHieu: str | None = None
    tenVanBan: str | None = None
    coQuanBanHanh: str | None = None
    loaiVanBan: str | None = None


class IndexingResult(BaseModel):
    """Kết quả sau khi nạp văn bản."""
    soHieu: str
    tenVanBan: str
    soChunks: int
    ngayIndex: datetime


class TrichDan(BaseModel):
    """Một trích dẫn pháp lý."""
    soHieu: str
    tenVanBan: str
    dieu: str | None = None
    khoan: str | None = None
    noiDungDayDu: str | None = None


class KetQuaTraLoi(BaseModel):
    """Response cho câu hỏi."""
    noiDung: str = Field(..., description="Câu trả lời markdown")
    trichDan: list[TrichDan] = Field(default_factory=list)
    doTinCay: str = Field(default="trung bình", description="cao | trung bình | thấp")
    chunksGoc: list[str] | None = Field(default=None, description="Fallback: chunk gốc khi LLM lỗi")


class QueryRequest(BaseModel):
    """Request body cho POST /api/query."""
    cauHoi: str = Field(..., min_length=1, max_length=1000)
