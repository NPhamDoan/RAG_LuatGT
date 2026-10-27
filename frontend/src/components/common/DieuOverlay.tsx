import type { TrichDan } from "../../types";

interface Props {
  trichDan: TrichDan;
  onClose: () => void;
}

export default function DieuOverlay({ trichDan, onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Nội dung ${trichDan.dieu || trichDan.soHieu}`}
    >
      <div
        className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="font-display text-lg font-semibold text-[var(--color-accent)]">
              {trichDan.dieu || "Trích dẫn"}
            </h3>
            <p className="mt-1 text-base text-[var(--color-text-muted)] font-mono">
              {trichDan.soHieu} — {trichDan.tenVanBan}
            </p>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 rounded-lg border border-[var(--color-border)] p-1.5 text-[var(--color-text-muted)] hover:bg-[var(--color-surface-3)] hover:text-[var(--color-text)] transition-colors cursor-pointer"
            aria-label="Đóng"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        {trichDan.noiDungDayDu ? (
          <div className="whitespace-pre-wrap text-base leading-relaxed text-[var(--color-text)]">
            {trichDan.noiDungDayDu}
          </div>
        ) : (
          <p className="text-base text-[var(--color-text-muted)] italic">
            Không có nội dung chi tiết.
          </p>
        )}
      </div>
    </div>
  );
}
