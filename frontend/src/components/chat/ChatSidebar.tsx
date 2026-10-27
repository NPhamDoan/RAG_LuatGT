import type { ChatSession } from "../../types";

interface Props {
  sessions: ChatSession[];
  currentId: string;
  collapsed: boolean;
  onToggle: () => void;
  onNew: () => void;
  onSwitch: (id: string) => void;
  onDelete: (id: string) => void;
}

/** Định dạng thời gian: hôm nay hiện giờ, khác ngày hiện dd/mm. */
function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}

export default function ChatSidebar({
  sessions,
  currentId,
  collapsed,
  onToggle,
  onNew,
  onSwitch,
  onDelete,
}: Props) {
  const ordered = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);

  if (collapsed) {
    return (
      <div className="flex h-full w-12 shrink-0 flex-col items-center gap-2 border-r border-[var(--color-border)] bg-[var(--color-surface-2)] py-3">
        <button
          onClick={onToggle}
          title="Mở lịch sử"
          className="rounded-lg p-2 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text)] cursor-pointer"
        >
          ☰
        </button>
        <button
          onClick={onNew}
          title="Cuộc trò chuyện mới"
          className="rounded-lg p-2 text-[var(--color-accent)] transition-colors hover:bg-[var(--color-accent)]/10 cursor-pointer"
        >
          +
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface-2)]">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 px-3 py-3">
        <span className="text-xs font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
          Lịch sử
        </span>
        <button
          onClick={onToggle}
          title="Thu gọn"
          className="rounded-lg p-1.5 text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text)] cursor-pointer"
        >
          ⟨
        </button>
      </div>

      {/* New chat */}
      <div className="px-3 pb-2">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-sm font-medium text-[var(--color-text)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] cursor-pointer"
        >
          <span className="text-base leading-none">+</span>
          Cuộc trò chuyện mới
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {ordered.length === 0 ? (
          <p className="px-2 py-4 text-xs text-[var(--color-text-muted)]">Chưa có cuộc nào.</p>
        ) : (
          <ul className="space-y-1">
            {ordered.map((s) => {
              const isActive = s.id === currentId;
              return (
                <li key={s.id}>
                  <div
                    onClick={() => onSwitch(s.id)}
                    className={`group flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 transition-colors ${
                      isActive
                        ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                        : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text)]"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{s.title}</p>
                      <p className="text-[11px] font-mono text-[var(--color-text-muted)]">
                        {formatTime(s.updatedAt)} · {s.messages.length} tin nhắn
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm(`Xóa cuộc trò chuyện "${s.title}"?`)) onDelete(s.id);
                      }}
                      title="Xóa"
                      className="shrink-0 rounded p-1 text-xs text-[var(--color-text-muted)] opacity-0 transition-opacity hover:text-[var(--color-danger)] group-hover:opacity-100 cursor-pointer"
                    >
                      ✕
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
