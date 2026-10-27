interface Props {
  onSuggestionClick: (text: string) => void;
}

const suggestions = [
  "Đường đôi là đường gì?",
  "Tốc độ tối đa được phép đi trong khu dân cư là bao nhiêu?",
  "Xe thô sơ là xe gì?",
  "Mức phạt vượt đèn đỏ đối với ô tô là bao nhiêu?",
  "Theo Điều 6 Nghị định 168/2024/NĐ-CP, ô tô không chấp hành hiệu lệnh của đèn tín hiệu giao thông bị phạt bao nhiêu?",
];

export default function WelcomeSuggestions({ onSuggestionClick }: Props) {
  return (
    <div className="flex flex-1 items-center justify-center px-4">
      <div className="w-full max-w-lg space-y-8 text-center">
        {/* Logo/Title */}
        <div className="space-y-2">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            <span className="text-[var(--color-accent)]">RAG</span>{" "}
            <span className="text-[var(--color-text)]">Luật Giao Thông</span>
          </h1>
          <p className="text-base text-[var(--color-text-muted)] font-mono">
            Tra cứu luật giao thông Việt Nam bằng AI
          </p>
        </div>

        {/* Suggestions */}
        <div className="space-y-2">
          <p className="text-xs font-mono uppercase tracking-wider text-[var(--color-text-muted)]">
            Câu hỏi gợi ý
          </p>
          <div className="grid gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSuggestionClick(s)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3 text-left text-base text-[var(--color-text-muted)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-text)] hover:bg-[var(--color-accent)]/5 cursor-pointer"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
