"""API routes: documents — upload / list / delete."""

import json
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.api.auth import require_admin
from app.api.dependencies import get_document_pipeline, get_index_deps, get_vector_store
from app.models.schemas import DocumentMetadataInput, DocumentUpdateInput, IndexingResult
from app.pipelines.document_pipeline import (
    DocumentPipeline,
    DocumentPipelineError,
    DuplicateDocumentError,
)
from app.storage.vector_store import PaginatedResult, VectorStore

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _parse_metadata(metadata: str) -> DocumentMetadataInput:
    try:
        return DocumentMetadataInput(**json.loads(metadata))
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Metadata không hợp lệ: {e}")


async def _build_enrich_override(
    enrich_mode: str,
    enrich_file: UploadFile | None,
    so_hieu: str,
) -> tuple[list, str | None]:
    """Dựng index_steps_override theo lựa chọn form. Trả (steps, cảnh báo)."""
    mode = (enrich_mode or "none").strip().lower()
    if mode == "none":
        return [], None
    if mode == "auto":
        from app.indexing.enrich_step import build_auto
        return [build_auto(get_index_deps())], None
    if mode == "manual":
        if enrich_file is None:
            raise HTTPException(status_code=400, detail="Enrich manual nhưng chưa chọn file enrich.")
        from app.indexing.enrich_io import parse_import_filtered
        from app.indexing.enrich_step import build_manual

        raw = await enrich_file.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File enrich không phải UTF-8.")
        try:
            enrich_by_seq, skipped = parse_import_filtered(text, so_hieu)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        warn = f"Đã bỏ qua {skipped} khối thuộc số hiệu khác." if skipped else None
        return [build_manual(so_hieu, enrich_by_seq)], warn
    raise HTTPException(status_code=400, detail=f"enrich_mode '{enrich_mode}' không hợp lệ.")


@router.post("", response_model=IndexingResult, status_code=201, dependencies=[Depends(require_admin)])
async def upload_document(
    file: UploadFile = File(...),
    metadata: Annotated[str, Form(...)] = ...,
    enrich_mode: Annotated[str, Form()] = "none",
    enrich_file: UploadFile | None = File(None),
    pipeline: DocumentPipeline = Depends(get_document_pipeline),
) -> IndexingResult:
    """Upload và index văn bản. enrich_mode: none | auto | manual (+ enrich_file khi manual)."""
    meta = _parse_metadata(metadata)
    content = await file.read()

    override, _warn = await _build_enrich_override(enrich_mode, enrich_file, meta.soHieu)

    try:
        return await pipeline.process_document(
            content, file.filename or "", meta, index_steps_override=override
        )
    except DuplicateDocumentError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except DocumentPipelineError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/enrich-export-upload", dependencies=[Depends(require_admin)])
async def enrich_export_upload(
    file: UploadFile = File(...),
    metadata: Annotated[str, Form(...)] = ...,
    pipeline: DocumentPipeline = Depends(get_document_pipeline),
) -> Response:
    """'Get chunk' cho PDF CHƯA NẠP: chunk file đang upload → file .txt để enrich ngoài."""
    from app.indexing.enrich_io import build_export_from_chunks

    meta = _parse_metadata(metadata)
    content = await file.read()
    try:
        chunks = pipeline.chunk_only(content, file.filename or "", meta)
        text, n = build_export_from_chunks(chunks, meta.soHieu)
    except (DocumentPipelineError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = f"enrich_{meta.soHieu.replace('/', '_')}.txt"
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Chunk-Count": str(n),
        },
    )


@router.get("")
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    store: VectorStore = Depends(get_vector_store),
) -> PaginatedResult:
    """Liệt kê văn bản đã nạp."""
    return await store.list_documents(page=page, page_size=page_size)


@router.get("/enrich-export", dependencies=[Depends(require_admin)])
async def enrich_export(so_hieu: str) -> Response:
    """Xuất chunk của MỘT văn bản ra file .txt (kèm prompt) để enrich bằng tool ngoài."""
    from app.indexing.enrich_io import build_export_text, get_enrich_file_path

    try:
        content, n = build_export_text(get_enrich_file_path(), so_hieu)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    safe = so_hieu.replace("/", "_")
    filename = f"enrich_{safe}.txt"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "X-Chunk-Count": str(n),
        },
    )


@router.patch("/{so_hieu:path}", status_code=200, dependencies=[Depends(require_admin)])
async def update_document(
    so_hieu: str,
    payload: DocumentUpdateInput,
    store: VectorStore = Depends(get_vector_store),
) -> dict:
    """Sửa metadata văn bản (tên, số hiệu, loại, cơ quan) — không re-index."""
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Không có trường nào để cập nhật.")

    new_so_hieu = updates.get("soHieu")
    if new_so_hieu is not None and not new_so_hieu.strip():
        raise HTTPException(status_code=400, detail="Số hiệu không được để trống.")

    # Đổi soHieu sang một số hiệu đã tồn tại (của văn bản khác) → chặn để không trộn 2 văn bản.
    if new_so_hieu and new_so_hieu != so_hieu and await store.exists(new_so_hieu):
        raise HTTPException(status_code=409, detail=f"Số hiệu '{new_so_hieu}' đã tồn tại.")

    updated = await store.update_document_metadata(so_hieu, updates)
    if updated == 0:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy văn bản '{so_hieu}'.")
    return {"message": f"Đã cập nhật {updated} chunks.", "soHieu": new_so_hieu or so_hieu}


@router.delete("/{so_hieu:path}", status_code=200, dependencies=[Depends(require_admin)])
async def delete_document(
    so_hieu: str,
    store: VectorStore = Depends(get_vector_store),
) -> dict:
    """Xóa văn bản theo số hiệu."""
    deleted = await store.delete_by_so_hieu(so_hieu)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy văn bản '{so_hieu}'.")
    return {"message": f"Đã xóa {deleted} chunks của '{so_hieu}'."}
