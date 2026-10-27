import { useState, type ReactNode } from "react";
import Markdown from "react-markdown";
import type { Message, TrichDan } from "../../types";
import ConfidenceBadge from "../common/ConfidenceBadge";
import DieuOverlay from "../common/DieuOverlay";
import TrichDanItem from "./TrichDanItem";

interface Props {
  message: Message;
}

/** Tách text, biến mỗi [n] thành nút bấm mở đúng đoạn trích dẫn [n].
 *  [n] ngoài phạm vi (LLM chèn số không có chip) → giữ text thường. */
function renderWithCitations(
  text: string,
  trichDan: TrichDan[],
  onCite: (index: number) => void,
): ReactNode[] {
  const parts: ReactNode[] = [];
  const re = /\[(\d+)\]/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    const n = parseInt(m[1], 10);
    const idx = n - 1;
    if (idx >= 0 && idx < trichDan.length) {
      parts.push(
        <button
          key={`cite-${key++}`}
          onClick={() => onCite(idx)}
          title={`Xem nguồn [${n}]: ${trichDan[idx].dieu || trichDan[idx].soHieu}`}
          className="mx-0.5 inline-flex items-center rounded bg-[var(--color-accent)]/15 px-1 align-super text-[0.7em] font-bold text-[var(--color-accent)] hover:bg-[var(--color-accent)]/30 cursor-pointer"
        >
          {n}
        </button>,
      );
    } else {
      // Số không khớp chip nào → giữ nguyên text [n] (không bấm được).
      parts.push(m[0]);
    }
    last = re.lastIndex;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

export default function MessageBubble({ message }: Props) {
  const [overlayIndex, setOverlayIndex] = useState<number | null>(null);

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-xl rounded-br-sm bg-[var(--color-accent-subtle)] border border-[var(--color-accent)]/20 px-4 py-2.5">
          <p className="text-base whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    );
  }

  const ketQua = message.ketQua;
  const trichDan = ketQua?.trichDan ?? [];

  // Xử lý children của 1 element markdown: thay string con bằng [n]-bấm-được.
  const withCitations = (children: ReactNode): ReactNode => {
    if (trichDan.length === 0) return children;
    const arr = Array.isArray(children) ? children : [children];
    return arr.map((child, i) =>
      typeof child === "string" ? (
        <span key={i}>{renderWithCitations(child, trichDan, setOverlayIndex)}</span>
      ) : (
        child
      ),
    );
  };

  // Áp cho các element hay chứa text citation (p, li, strong, em).
  const citationComponents = {
    p: ({ children }: { children?: ReactNode }) => <p>{withCitations(children)}</p>,
    li: ({ children }: { children?: ReactNode }) => <li>{withCitations(children)}</li>,
    strong: ({ children }: { children?: ReactNode }) => <strong>{withCitations(children)}</strong>,
    em: ({ children }: { children?: ReactNode }) => <em>{withCitations(children)}</em>,
  };

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-3">
        {/* Badge */}
        {ketQua && (
          <ConfidenceBadge level={ketQua.doTinCay} />
        )}

        {/* Content — [n] trong text thành nút bấm mở đúng đoạn nguồn [n] */}
        <div className="rounded-xl rounded-bl-sm border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
          <div className="markdown-content">
            <Markdown components={citationComponents}>{message.content}</Markdown>
          </div>
        </div>

        {/* Fallback chunks */}
        {ketQua?.chunksGoc && ketQua.chunksGoc.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-mono text-[var(--color-text-muted)]">Các đoạn luật liên quan:</p>
            {ketQua.chunksGoc.map((chunk, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] p-3 text-xs leading-relaxed"
              >
                {chunk}
              </div>
            ))}
          </div>
        )}

        {/* Citations */}
        {ketQua && ketQua.trichDan.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {ketQua.trichDan.map((td, i) => (
              <TrichDanItem
                key={i}
                index={i}
                trichDan={td}
                onClick={() => setOverlayIndex(i)}
              />
            ))}
          </div>
        )}

        {/* Overlay */}
        {overlayIndex !== null && ketQua && (
          <DieuOverlay
            trichDan={ketQua.trichDan[overlayIndex]}
            onClose={() => setOverlayIndex(null)}
          />
        )}
      </div>
    </div>
  );
}
