import { useState, type FormEvent, type KeyboardEvent } from "react";

interface Props {
  onSend: (text: string) => void;
  disabled?: boolean;
}

const MAX_LENGTH = 500;

export default function ChatInput({ onSend, disabled = false }: Props) {
  const [text, setText] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="flex items-end gap-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-2 transition-colors focus-within:border-[var(--color-accent)]">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value.slice(0, MAX_LENGTH))}
          onKeyDown={handleKeyDown}
          placeholder="Nhập câu hỏi về luật giao thông..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none bg-transparent px-2 py-1.5 text-base text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none disabled:opacity-50"
          style={{ minHeight: "36px", maxHeight: "120px" }}
        />
        <button
          type="submit"
          disabled={disabled || !text.trim()}
          className="shrink-0 rounded-lg bg-[var(--color-accent)] px-3 py-1.5 text-base font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
        >
          Gửi
        </button>
      </div>
      <div className="mt-1 text-right text-[10px] font-mono text-[var(--color-text-muted)]">
        {text.length}/{MAX_LENGTH}
      </div>
    </form>
  );
}
