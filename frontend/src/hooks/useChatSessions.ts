import { useCallback, useEffect, useState } from "react";
import client from "../api/client";
import type { ChatSession, KetQuaTraLoi, Message } from "../types";
import { loadSessions, saveSessions } from "../utils/chatStorage";

/** Giới hạn số tin nhắn giữ trong 1 session. */
const MAX_MESSAGES_PER_SESSION = 100;

/** Tiêu đề mặc định cho cuộc trò chuyện chưa có nội dung. */
const DEFAULT_TITLE = "Cuộc trò chuyện mới";

/** Sinh tiêu đề từ câu hỏi đầu tiên (cắt ngắn nếu dài). */
function makeTitle(cauHoi: string): string {
  const t = cauHoi.trim().replace(/\s+/g, " ");
  return t.length > 60 ? `${t.slice(0, 60)}…` : t;
}

/** Tạo một session rỗng mới. */
function createSession(): ChatSession {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    title: DEFAULT_TITLE,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

/**
 * Quản lý các cuộc trò chuyện + gọi API /api/query.
 * Lưu tự động vào localStorage (chỉ session đã có tin nhắn).
 * Mỗi lần mở app bắt đầu bằng 1 cuộc trò chuyện mới (rỗng), các cuộc cũ nằm ở sidebar.
 */
export function useChatSessions() {
  // Khởi tạo 1 lần: session mới rỗng + các session đã lưu.
  const [initial] = useState(() => {
    const loaded = loadSessions();
    const fresh = createSession();
    return { sessions: [fresh, ...loaded], currentId: fresh.id };
  });
  const [sessions, setSessions] = useState<ChatSession[]>(initial.sessions);
  const [currentId, setCurrentId] = useState<string>(initial.currentId);
  const [loading, setLoading] = useState(false);

  // Chỉ lưu các session đã có tin nhắn (bỏ session rỗng).
  useEffect(() => {
    saveSessions(sessions.filter((s) => s.messages.length > 0));
  }, [sessions]);

  // Luôn đảm bảo có ít nhất 1 session và currentId hợp lệ.
  useEffect(() => {
    if (sessions.length === 0) {
      const fresh = createSession();
      setSessions([fresh]);
      setCurrentId(fresh.id);
    } else if (!sessions.some((s) => s.id === currentId)) {
      setCurrentId(sessions[0].id);
    }
  }, [sessions, currentId]);

  const currentSession = sessions.find((s) => s.id === currentId) ?? null;
  const messages = currentSession?.messages ?? [];

  const newSession = useCallback(() => {
    const fresh = createSession();
    // Bỏ các session rỗng cũ, thêm session mới lên đầu.
    setSessions((prev) => [fresh, ...prev.filter((s) => s.messages.length > 0)]);
    setCurrentId(fresh.id);
  }, []);

  const switchSession = useCallback((id: string) => {
    // Chuyển sang session id; đồng thời dọn session rỗng đang mở dở.
    setSessions((prev) => prev.filter((s) => s.messages.length > 0 || s.id === id));
    setCurrentId(id);
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const sendQuery = useCallback(
    async (cauHoi: string) => {
      const targetId = currentId;
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: cauHoi,
        timestamp: Date.now(),
      };

      setSessions((prev) =>
        prev.map((s) =>
          s.id === targetId
            ? {
                ...s,
                title: s.messages.length === 0 ? makeTitle(cauHoi) : s.title,
                messages: [...s.messages, userMsg].slice(-MAX_MESSAGES_PER_SESSION),
                updatedAt: Date.now(),
              }
            : s,
        ),
      );
      setLoading(true);

      try {
        const { data } = await client.post<KetQuaTraLoi>("/api/query", { cauHoi });
        const assistantMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.noiDung,
          ketQua: data,
          timestamp: Date.now(),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === targetId
              ? {
                  ...s,
                  messages: [...s.messages, assistantMsg].slice(-MAX_MESSAGES_PER_SESSION),
                  updatedAt: Date.now(),
                }
              : s,
          ),
        );
      } catch (err) {
        console.error("[useChatSessions] Lỗi gọi /api/query:", err);
        const errorMsg: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "Không thể kết nối đến máy chủ. Vui lòng thử lại.",
          timestamp: Date.now(),
        };
        setSessions((prev) =>
          prev.map((s) =>
            s.id === targetId
              ? {
                  ...s,
                  messages: [...s.messages, errorMsg].slice(-MAX_MESSAGES_PER_SESSION),
                  updatedAt: Date.now(),
                }
              : s,
          ),
        );
      } finally {
        setLoading(false);
      }
    },
    [currentId],
  );

  return {
    messages,
    loading,
    sendQuery,
    sessions,
    currentId,
    newSession,
    switchSession,
    deleteSession,
  };
}
