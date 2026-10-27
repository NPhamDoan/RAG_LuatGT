import type { TrichDan } from "../../types";

interface Props {
  index: number;
  trichDan: TrichDan;
  onClick: () => void;
}

export default function TrichDanItem({ index, trichDan, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="group inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-2.5 py-1.5 text-xs font-mono transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 cursor-pointer"
      title={`${trichDan.tenVanBan || trichDan.soHieu}${trichDan.dieu ? ` — ${trichDan.dieu}` : ""}${trichDan.khoan ? `, ${trichDan.khoan}` : ""}`}
    >
      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[var(--color-accent)]/20 text-[10px] font-bold text-[var(--color-accent)]">
        {index + 1}
      </span>
      <span className="flex items-center gap-1 truncate max-w-[240px] text-[var(--color-text-muted)] group-hover:text-[var(--color-text)]">
        <span>{trichDan.dieu || trichDan.soHieu}</span>
        {trichDan.dieu && trichDan.soHieu && (
          <span className="text-[var(--color-accent)]/80">· {trichDan.soHieu}</span>
        )}
      </span>
    </button>
  );
}
