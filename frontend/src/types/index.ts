/** Một trích dẫn pháp lý. */
export interface TrichDan {
  soHieu: string;
  tenVanBan: string;
  dieu: string | null;
  khoan: string | null;
  noiDungDayDu: string | null;
}

/** Response từ POST /api/query. */
export interface KetQuaTraLoi {
  noiDung: string;
  trichDan: TrichDan[];
  doTinCay: "cao" | "trung bình" | "thấp";
  chunksGoc: string[] | null;
}

/** Một tin nhắn trong lịch sử chat. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  ketQua?: KetQuaTraLoi;
  timestamp: number;
}

/** Một cuộc trò chuyện đã lưu (localStorage). */
export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

/** Metadata văn bản đã nạp (kèm thông tin lần nạp per-document). */
export interface DocumentMetadata {
  soHieu: string;
  tenVanBan: string;
  ngayBanHanh: string;
  ngayHieuLuc: string;
  coQuanBanHanh: string;
  loaiVanBan: string;
  soChunks?: number;
  ngayIndex?: string;
  // Seed info per-document (có khi văn bản được nạp sau khi có tính năng ghi nhãn).
  seedVersion?: number;
  seedAt?: string;
  seedIndexSteps?: string;
  seedEnrichEnabled?: boolean;
  seedEnrichSource?: string;
  seedEnrichModel?: string;
  seedRetrieval?: string;
  seedEmbedding?: string;
}

/** Response phân trang danh sách văn bản. */
export interface PaginatedDocuments {
  items: DocumentMetadata[];
  total: number;
  page: number;
  pageSize: number;
}


