import { useEffect, useState, type FormEvent } from "react";
import type { useDocuments } from "../hooks/useDocuments";
import type { UploadJob } from "../hooks/useDocuments";
import type { DocumentMetadata } from "../types";

interface Props {
  documentsState: ReturnType<typeof useDocuments>;
}

export default function AdminPage({ documentsState }: Props) {
  const {
    documents,
    total,
    loading,
    jobs,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    updateDocument,
    getChunkForUpload,
    getChunkForExisting,
    clearDoneJobs,
    clearJob,
  } = documentsState;

  // Sửa metadata văn bản (inline)
  const [editingSoHieu, setEditingSoHieu] = useState<string | null>(null);
  const [editSoHieu, setEditSoHieu] = useState("");
  const [editTenVanBan, setEditTenVanBan] = useState("");
  const [editLoaiVanBan, setEditLoaiVanBan] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const [file, setFile] = useState<File | null>(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [soHieu, setSoHieu] = useState("");
  const [tenVanBan, setTenVanBan] = useState("");
  const [ngayBanHanh, setNgayBanHanh] = useState("");
  const [ngayHieuLuc, setNgayHieuLuc] = useState("");
  const [coQuanBanHanh, setCoQuanBanHanh] = useState("");
  const [loaiVanBan, setLoaiVanBan] = useState("");

  // Enrich khi upload: none | auto | manual
  const [enrichMode, setEnrichMode] = useState<"none" | "auto" | "manual">("none");
  const [enrichFile, setEnrichFile] = useState<File | null>(null);
  const [enrichFileKey, setEnrichFileKey] = useState(0);
  const [getChunkMsg, setGetChunkMsg] = useState("");
  const [gettingChunk, setGettingChunk] = useState(false);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Auto refresh + auto clear done jobs
  const doneCount = jobs.filter((j) => j.status === "done").length;
  useEffect(() => {
    if (doneCount > 0) {
      fetchDocuments();
      // Tự xóa job done sau 2 giây (đã hiện trong "Văn bản đã nạp")
      const timer = setTimeout(() => clearDoneJobs(), 2000);
      return () => clearTimeout(timer);
    }
  }, [doneCount, fetchDocuments, clearDoneJobs]);

  const currentMetadata = (): Omit<DocumentMetadata, "soChunks" | "ngayIndex"> => ({
    soHieu,
    tenVanBan,
    ngayBanHanh,
    ngayHieuLuc,
    coQuanBanHanh,
    loaiVanBan,
  });

  const handleUpload = (e: FormEvent) => {
    e.preventDefault();
    if (!file || !soHieu || !tenVanBan || !ngayBanHanh || !ngayHieuLuc) return;
    if (enrichMode === "manual" && !enrichFile) {
      setGetChunkMsg("Enrich manual: cần chọn file đã điền enrich trước khi tải lên.");
      return;
    }

    // Fire and forget — queue-based
    uploadDocument(file, currentMetadata(), enrichMode, enrichFile);

    // Reset form ngay để upload file khác
    setFile(null);
    setFileInputKey((k) => k + 1);
    setSoHieu("");
    setTenVanBan("");
    setNgayBanHanh("");
    setNgayHieuLuc("");
    setCoQuanBanHanh("");
    setLoaiVanBan("");
    setEnrichMode("none");
    setEnrichFile(null);
    setEnrichFileKey((k) => k + 1);
    setGetChunkMsg("");
  };

  // "Get chunk" cho PDF đang chọn trong form (chưa nạp).
  const handleGetChunkUpload = async () => {
    if (!file || !soHieu || !tenVanBan || !ngayBanHanh || !ngayHieuLuc) {
      setGetChunkMsg("Cần chọn file PDF và điền số hiệu/tên/ngày trước khi lấy chunk.");
      return;
    }
    setGettingChunk(true);
    setGetChunkMsg("");
    const err = await getChunkForUpload(file, currentMetadata());
    setGettingChunk(false);
    setGetChunkMsg(err || "Đã tải file chunk. Điền enrich bằng tool ngoài rồi quay lại chọn file.");
  };

  const handleDelete = async (soHieu: string) => {
    if (!confirm(`Xóa văn bản "${soHieu}"?`)) return;
    const ok = await deleteDocument(soHieu);
    if (ok) fetchDocuments();
  };

  const startEdit = (doc: DocumentMetadata) => {
    setEditingSoHieu(doc.soHieu);
    setEditSoHieu(doc.soHieu);
    setEditTenVanBan(doc.tenVanBan);
    setEditLoaiVanBan(doc.loaiVanBan || "");
    setEditError("");
  };

  const cancelEdit = () => {
    setEditingSoHieu(null);
    setEditError("");
  };

  const saveEdit = async (originalSoHieu: string) => {
    if (!editSoHieu.trim() || !editTenVanBan.trim()) return;
    setEditSaving(true);
    setEditError("");
    const ok = await updateDocument(originalSoHieu, {
      soHieu: editSoHieu.trim(),
      tenVanBan: editTenVanBan.trim(),
      loaiVanBan: editLoaiVanBan.trim(),
    });
    setEditSaving(false);
    if (ok) {
      setEditingSoHieu(null);
      fetchDocuments();
    } else {
      setEditError("Cập nhật thất bại — số hiệu mới có thể đã tồn tại.");
    }
  };

  return (
    <div className="h-full overflow-y-auto px-4 py-6">
      <div className="mx-auto max-w-4xl space-y-8">
        {/* Header */}
        <div>
          <h1 className="font-display text-2xl font-bold">Quản lý văn bản</h1>
          <p className="mt-1 text-base text-[var(--color-text-muted)] font-mono">
            Tải lên và quản lý văn bản luật giao thông
          </p>
        </div>

        {/* Upload Queue — đang xử lý */}
        {jobs.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-lg font-semibold">Đang xử lý</h2>
            </div>
            <div className="space-y-2">
              {jobs.map((job) => (
                <JobItem key={job.id} job={job} onClear={() => clearJob(job.id)} />
              ))}
            </div>
          </div>
        )}

        {/* Upload form */}
        <form onSubmit={handleUpload} className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-6">
          <h2 className="font-display text-lg font-semibold">Tải lên văn bản mới</h2>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Số hiệu *</label>
              <input
                type="text"
                value={soHieu}
                onChange={(e) => setSoHieu(e.target.value)}
                placeholder="36/2024/QH15"
                required
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Tên văn bản *</label>
              <input
                type="text"
                value={tenVanBan}
                onChange={(e) => setTenVanBan(e.target.value)}
                placeholder="Luật TTATGT đường bộ 2024"
                required
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Ngày ban hành *</label>
              <input
                type="date"
                value={ngayBanHanh}
                onChange={(e) => setNgayBanHanh(e.target.value)}
                required
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Ngày hiệu lực *</label>
              <input
                type="date"
                value={ngayHieuLuc}
                onChange={(e) => setNgayHieuLuc(e.target.value)}
                required
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Cơ quan ban hành</label>
              <input
                type="text"
                value={coQuanBanHanh}
                onChange={(e) => setCoQuanBanHanh(e.target.value)}
                placeholder="Quốc hội"
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Loại văn bản</label>
              <input
                type="text"
                value={loaiVanBan}
                onChange={(e) => setLoaiVanBan(e.target.value)}
                placeholder="Luật"
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-base text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
          </div>

          {/* File input */}
          <div>
            <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">File PDF/TXT *</label>
            <input
              key={fileInputKey}
              type="file"
              accept=".pdf,.txt"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              required
              className="w-full text-base text-[var(--color-text-muted)] file:mr-3 file:rounded-lg file:border file:border-[var(--color-border)] file:bg-[var(--color-surface-3)] file:px-3 file:py-1.5 file:text-xs file:font-mono file:text-[var(--color-text)] file:cursor-pointer hover:file:bg-[var(--color-accent)]/10"
            />
          </div>

          {/* Enrich mode */}
          <div className="space-y-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)]/40 p-3">
            <label className="block text-xs font-mono text-[var(--color-text-muted)]">Làm giàu dữ liệu (enrich)</label>
            <div className="flex flex-wrap gap-4 text-sm">
              {([
                ["none", "Không enrich"],
                ["auto", "Tự động (LLM)"],
                ["manual", "Thủ công (file)"],
              ] as const).map(([val, label]) => (
                <label key={val} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="enrichMode"
                    checked={enrichMode === val}
                    onChange={() => {
                      setEnrichMode(val);
                      setGetChunkMsg("");
                    }}
                  />
                  <span>{label}</span>
                </label>
              ))}
            </div>

            {enrichMode === "manual" && (
              <div className="space-y-2 border-t border-[var(--color-border)] pt-2">
                <p className="text-xs text-[var(--color-text-muted)]">
                  1. Lấy chunk của file đang chọn → điền enrich bằng NotebookLM → 2. chọn file đã điền.
                </p>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleGetChunkUpload}
                    disabled={gettingChunk}
                    className="rounded-lg border border-[var(--color-accent)]/40 px-3 py-1.5 text-xs font-mono text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 disabled:opacity-40 cursor-pointer"
                  >
                    {gettingChunk ? "Đang lấy..." : "1. Get chunk (.txt)"}
                  </button>
                  <label className="text-xs font-mono text-[var(--color-text-muted)]">
                    2. File enrich:
                  </label>
                  <input
                    key={enrichFileKey}
                    type="file"
                    accept=".txt"
                    onChange={(e) => setEnrichFile(e.target.files?.[0] || null)}
                    className="text-xs text-[var(--color-text-muted)] file:mr-2 file:rounded file:border file:border-[var(--color-border)] file:bg-[var(--color-surface-3)] file:px-2 file:py-1 file:text-xs file:text-[var(--color-text)] file:cursor-pointer"
                  />
                </div>
                {enrichFile && (
                  <p className="text-xs font-mono text-[var(--color-success)]">Đã chọn: {enrichFile.name}</p>
                )}
              </div>
            )}
            {getChunkMsg && (
              <p className="text-xs font-mono text-[var(--color-text-muted)]">{getChunkMsg}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={!file || !soHieu || !tenVanBan || !ngayBanHanh || !ngayHieuLuc}
            className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-base font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          >
            Tải lên
          </button>
        </form>

        {/* Document list */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-semibold">Văn bản đã nạp</h2>
            <span className="text-xs font-mono text-[var(--color-text-muted)]">{total} văn bản</span>
          </div>

          {loading ? (
            <p className="text-base text-[var(--color-text-muted)] font-mono">Đang tải danh sách...</p>
          ) : documents.length === 0 ? (
            <p className="text-base text-[var(--color-text-muted)]">Chưa có văn bản nào.</p>
          ) : (
            <div className="space-y-2">
              {documents.map((doc) =>
                editingSoHieu === doc.soHieu ? (
                  <div
                    key={doc.soHieu}
                    className="space-y-3 rounded-lg border border-[var(--color-accent)]/40 bg-[var(--color-surface-2)] px-4 py-3"
                  >
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Số hiệu *</label>
                        <input
                          type="text"
                          value={editSoHieu}
                          onChange={(e) => setEditSoHieu(e.target.value)}
                          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
                        />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Loại văn bản</label>
                        <input
                          type="text"
                          value={editLoaiVanBan}
                          onChange={(e) => setEditLoaiVanBan(e.target.value)}
                          placeholder="Luật"
                          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)]"
                        />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="mb-1 block text-xs font-mono text-[var(--color-text-muted)]">Tên văn bản *</label>
                        <input
                          type="text"
                          value={editTenVanBan}
                          onChange={(e) => setEditTenVanBan(e.target.value)}
                          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)] px-3 py-2 text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent)]"
                        />
                      </div>
                    </div>
                    {editError && (
                      <p className="text-xs font-mono text-[var(--color-danger)]">{editError}</p>
                    )}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => saveEdit(doc.soHieu)}
                        disabled={editSaving || !editSoHieu.trim() || !editTenVanBan.trim()}
                        className="rounded-lg bg-[var(--color-accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                      >
                        {editSaving ? "Đang lưu..." : "Lưu"}
                      </button>
                      <button
                        onClick={cancelEdit}
                        disabled={editSaving}
                        className="rounded-lg border border-[var(--color-border)] px-3 py-1.5 text-xs font-mono text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)] cursor-pointer"
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                ) : (
                  <div
                    key={doc.soHieu}
                    className="flex items-center justify-between gap-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-base font-medium truncate">{doc.tenVanBan}</p>
                      <p className="text-xs font-mono text-[var(--color-text-muted)]">
                        {doc.soHieu} · {doc.loaiVanBan || "—"} · {doc.soChunks ?? "?"} chunks
                      </p>
                      <SeedInfo doc={doc} />
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <button
                        onClick={() => getChunkForExisting(doc.soHieu)}
                        title="Tải file chunk để enrich (không chunk lại)"
                        className="rounded-lg border border-[var(--color-border)] px-2.5 py-1 text-xs font-mono text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-accent)] hover:border-[var(--color-accent)]/30 cursor-pointer"
                      >
                        Lấy chunk
                      </button>
                      <button
                        onClick={() => startEdit(doc)}
                        className="rounded-lg border border-[var(--color-border)] px-2.5 py-1 text-xs font-mono text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-accent)] hover:border-[var(--color-accent)]/30 cursor-pointer"
                      >
                        Sửa
                      </button>
                      <button
                        onClick={() => handleDelete(doc.soHieu)}
                        className="rounded-lg border border-[var(--color-border)] px-2.5 py-1 text-xs font-mono text-[var(--color-danger)] transition-colors hover:bg-[var(--color-danger)]/10 hover:border-[var(--color-danger)]/30 cursor-pointer"
                      >
                        Xóa
                      </button>
                    </div>
                  </div>
                ),
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

/* === Job status item === */
function JobItem({ job, onClear }: { job: UploadJob; onClear: () => void }) {
  const statusConfig = {
    uploading: { label: "Đang tải lên", color: "text-[var(--color-accent)]", pulse: true },
    processing: { label: "Đang phân tích văn bản", color: "text-[var(--color-warning)]", pulse: true },
    done: { label: "Hoàn tất", color: "text-[var(--color-success)]", pulse: false },
    error: { label: "Thất bại", color: "text-[var(--color-danger)]", pulse: false },
  };

  const cfg = statusConfig[job.status];

  return (
    <div className="flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-3">
      {/* Pulse dot */}
      <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${cfg.pulse ? "animate-pulse" : ""} ${
        job.status === "uploading" ? "bg-[var(--color-accent)]" :
        job.status === "processing" ? "bg-[var(--color-warning)]" :
        job.status === "done" ? "bg-[var(--color-success)]" :
        "bg-[var(--color-danger)]"
      }`} />

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{job.tenVanBan || job.filename}</p>
        <p className="text-xs font-mono text-[var(--color-text-muted)]">
          {job.filename} · {job.soHieu} · <span className={cfg.color}>{cfg.label}</span>
          {job.status === "uploading" && ` (${job.progress}%)`}
          {job.error && ` — ${job.error}`}
        </p>
        {/* Progress bar */}
        {(job.status === "uploading" || job.status === "processing") && (
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--color-surface-3)]">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                job.status === "processing" ? "bg-[var(--color-warning)] animate-pulse" : "bg-[var(--color-accent)]"
              }`}
              style={{ width: job.status === "processing" ? "100%" : `${job.progress}%` }}
            />
          </div>
        )}
      </div>

      {/* Clear button (only done/error) */}
      {(job.status === "done" || job.status === "error") && (
        <button
          onClick={onClear}
          className="shrink-0 text-xs font-mono text-[var(--color-text-muted)] hover:text-[var(--color-text)] cursor-pointer"
          title="Xóa khỏi danh sách"
        >
          ✕
        </button>
      )}
    </div>
  );
}

/* === Thông tin lần nạp CỦA TỪNG VĂN BẢN (bung ra xem chi tiết) === */
function SeedInfo({ doc }: { doc: DocumentMetadata }) {
  const [open, setOpen] = useState(false);

  // Văn bản nạp trước khi có tính năng ghi nhãn → không có seedAt.
  if (!doc.seedAt) {
    return (
      <p className="mt-1 text-xs font-mono text-[var(--color-warning)]">
        chưa có nhãn nạp (nạp lại để ghi)
      </p>
    );
  }

  const enriched = !!doc.seedEnrichEnabled;
  const seedAt = (() => {
    const d = new Date(doc.seedAt);
    return isNaN(d.getTime()) ? doc.seedAt! : d.toLocaleString("vi-VN");
  })();
  const enrichValue = enriched
    ? `Bật${
        doc.seedEnrichSource
          ? ` (${doc.seedEnrichSource}${doc.seedEnrichModel ? `: ${doc.seedEnrichModel}` : ""})`
          : ""
      }`
    : "Tắt";

  const rows: { label: string; value: string }[] = [
    { label: "Version", value: `v${doc.seedVersion ?? "?"}` },
    { label: "Thời điểm nạp", value: seedAt },
    { label: "Enrich", value: enrichValue },
    { label: "Index steps", value: doc.seedIndexSteps || "—" },
    { label: "Retrieval", value: doc.seedRetrieval || "—" },
    { label: "Embedding", value: doc.seedEmbedding || "—" },
  ];

  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 text-xs font-mono text-[var(--color-text-muted)] hover:text-[var(--color-text)] cursor-pointer"
      >
        <span
          className={`rounded-full px-2 py-0.5 ${
            enriched
              ? "bg-[var(--color-success)]/15 text-[var(--color-success)]"
              : "bg-[var(--color-surface-3)] text-[var(--color-text-muted)]"
          }`}
        >
          {enriched ? "enriched" : "chưa enrich"}
        </span>
        <span>· nạp {seedAt}</span>
        <span className="opacity-60">{open ? "▲ ẩn" : "▼ chi tiết"}</span>
      </button>

      {open && (
        <dl className="mt-2 grid gap-x-6 gap-y-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-3)]/40 px-3 py-2 sm:grid-cols-2">
          {rows.map((r) => (
            <div key={r.label} className="flex items-baseline justify-between gap-3">
              <dt className="shrink-0 text-xs font-mono text-[var(--color-text-muted)]">{r.label}</dt>
              <dd
                className="min-w-0 truncate text-right text-xs text-[var(--color-text)]"
                title={r.value}
              >
                {r.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
