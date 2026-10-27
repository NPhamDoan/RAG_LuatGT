import { useCallback, useState, useRef } from "react";
import client from "../api/client";
import type { DocumentMetadata, PaginatedDocuments } from "../types";

export type UploadStatus = "uploading" | "processing" | "done" | "error";

/** Các trường metadata cho phép sửa (chỉ gửi trường muốn đổi). */
export interface DocumentUpdate {
  soHieu?: string;
  tenVanBan?: string;
  loaiVanBan?: string;
  coQuanBanHanh?: string;
}

export interface UploadJob {
  id: string;
  filename: string;
  soHieu: string;
  tenVanBan: string;
  status: UploadStatus;
  progress: number;
  error?: string;
}

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const jobIdRef = useRef(0);

  const fetchDocuments = useCallback(async (page = 1, pageSize = 20) => {
    setLoading(true);
    try {
      const { data } = await client.get<PaginatedDocuments>("/api/documents", {
        params: { page, page_size: pageSize },
      });
      setDocuments(data.items);
      setTotal(data.total);
    } catch {
      setDocuments([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, []);



  const uploadDocument = useCallback(
    async (
      file: File,
      metadata: Omit<DocumentMetadata, "soChunks" | "ngayIndex">,
      enrichMode: "none" | "auto" | "manual" = "none",
      enrichFile?: File | null,
    ) => {
      const id = String(++jobIdRef.current);
      const job: UploadJob = {
        id,
        filename: file.name,
        soHieu: metadata.soHieu,
        tenVanBan: metadata.tenVanBan,
        status: "uploading",
        progress: 0,
      };

      setJobs((prev) => [job, ...prev]);

      const formData = new FormData();
      formData.append("file", file);
      formData.append("metadata", JSON.stringify(metadata));
      formData.append("enrich_mode", enrichMode);
      if (enrichMode === "manual" && enrichFile) {
        formData.append("enrich_file", enrichFile);
      }

      try {
        // Upload phase
        await client.post("/api/documents", formData, {
          headers: { "Content-Type": "multipart/form-data" },
          timeout: 0,
          onUploadProgress: (e) => {
            const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
            setJobs((prev) =>
              prev.map((j) =>
                j.id === id
                  ? { ...j, progress: pct, status: pct >= 100 ? "processing" : "uploading" }
                  : j,
              ),
            );
          },
        });

        // Done
        setJobs((prev) =>
          prev.map((j) => (j.id === id ? { ...j, status: "done", progress: 100 } : j)),
        );
      } catch (err: unknown) {
        const anyErr = err as { response?: { data?: { detail?: string } }; message?: string };
        const message = anyErr.response?.data?.detail || anyErr.message || "Upload thất bại";
        setJobs((prev) =>
          prev.map((j) => (j.id === id ? { ...j, status: "error", error: message } : j)),
        );
      }
    },
    [],
  );

  const clearDoneJobs = useCallback(() => {
    setJobs((prev) => prev.filter((j) => j.status !== "done"));
  }, []);

  const clearJob = useCallback((id: string) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
  }, []);

  const _downloadBlob = (data: BlobPart, soHieu: string) => {
    const blob = new Blob([data], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `enrich_${soHieu.replace(/\//g, "_")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // "Get chunk" cho PDF ĐANG CHỌN trong form (chưa nạp) → tải .txt để enrich ngoài.
  const getChunkForUpload = useCallback(
    async (
      file: File,
      metadata: Omit<DocumentMetadata, "soChunks" | "ngayIndex">,
    ): Promise<string | null> => {
      const form = new FormData();
      form.append("file", file);
      form.append("metadata", JSON.stringify(metadata));
      try {
        const res = await client.post(`/api/documents/enrich-export-upload`, form, {
          headers: { "Content-Type": "multipart/form-data" },
          responseType: "blob",
        });
        _downloadBlob(res.data, metadata.soHieu);
        return null;
      } catch {
        return "Lấy chunk thất bại — kiểm tra file PDF và số hiệu.";
      }
    },
    [],
  );

  // "Lấy chunk" cho văn bản ĐÃ NẠP → tải .txt (không chunk lại).
  const getChunkForExisting = useCallback(async (soHieu: string): Promise<string | null> => {
    try {
      const res = await client.get(`/api/documents/enrich-export`, {
        params: { so_hieu: soHieu },
        responseType: "blob",
      });
      _downloadBlob(res.data, soHieu);
      return null;
    } catch {
      return "Lấy chunk thất bại — văn bản có thể chưa có trong file enrich.";
    }
  }, []);

  const deleteDocument = useCallback(async (soHieu: string) => {
    try {
      await client.delete(`/api/documents/${soHieu}`);
      return true;
    } catch {
      return false;
    }
  }, []);

  const updateDocument = useCallback(
    async (soHieu: string, updates: DocumentUpdate) => {
      try {
        await client.patch(`/api/documents/${soHieu}`, updates);
        return true;
      } catch {
        return false;
      }
    },
    [],
  );

  return {
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
  };
}
