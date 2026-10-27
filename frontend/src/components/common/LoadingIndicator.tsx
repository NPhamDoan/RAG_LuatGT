export default function LoadingIndicator() {
  return (
    <div className="flex items-center gap-2 px-4 py-3">
      <div className="flex gap-1">
        <span className="h-2 w-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
        <span className="h-2 w-2 rounded-full bg-[var(--color-accent)] animate-pulse [animation-delay:150ms]" />
        <span className="h-2 w-2 rounded-full bg-[var(--color-accent)] animate-pulse [animation-delay:300ms]" />
      </div>
      <span className="text-base text-[var(--color-text-muted)] font-mono">
        Đang tìm câu trả lời...
      </span>
    </div>
  );
}
