interface Props {
  level: "cao" | "trung bình" | "thấp";
}

const config = {
  cao: { label: "Độ tin tưởng cao", cls: "bg-[var(--color-success)]/15 text-[var(--color-success)] border-[var(--color-success)]/30" },
  "trung bình": { label: "Độ tin tưởng trung bình", cls: "bg-[var(--color-warning)]/15 text-[var(--color-warning)] border-[var(--color-warning)]/30" },
  thấp: { label: "Độ tin tưởng thấp", cls: "bg-[var(--color-danger)]/15 text-[var(--color-danger)] border-[var(--color-danger)]/30" },
};

export default function ConfidenceBadge({ level }: Props) {
  const { label, cls } = config[level];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-mono font-medium ${cls}`}>
      {label}
    </span>
  );
}
