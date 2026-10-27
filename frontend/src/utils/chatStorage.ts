import type { ChatSession } from "../types";

/** Key localStorage lưu danh sách cuộc trò chuyện. */
const STORAGE_KEY = "rag-gt-chat-sessions";

/** Giới hạn số cuộc trò chuyện giữ lại (tránh phình localStorage). */
const MAX_SESSIONS = 50;

/** Đọc danh sách session từ localStorage. Lỗi/parse hỏng → trả mảng rỗng. */
export function loadSessions(): ChatSession[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as ChatSession[];
  } catch (err) {
    console.error("[chatStorage] Không đọc được lịch sử chat từ localStorage:", err);
    return [];
  }
}

/** Ghi danh sách session xuống localStorage (chỉ giữ MAX_SESSIONS gần nhất). */
export function saveSessions(sessions: ChatSession[]): void {
  try {
    const trimmed = sessions.slice(0, MAX_SESSIONS);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch (err) {
    console.error("[chatStorage] Không lưu được lịch sử chat vào localStorage:", err);
  }
}
