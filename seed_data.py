"""Seed du lieu: nap cac file luat trong data/seed/ vao ChromaDB (khong can UI).

Chay tu goc du an (dung venv cua backend):
    backend\\.venv\\Scripts\\python.exe seed_data.py            # nap (bao qua neu trung)
    backend\\.venv\\Scripts\\python.exe seed_data.py --replace  # ghi de van ban trung
    backend\\.venv\\Scripts\\python.exe seed_data.py --reset    # xoa sach DB roi nap lai
    backend\\.venv\\Scripts\\python.exe seed_data.py --dry-run  # chi liet ke, khong nap

Pipeline giong het upload qua UI: parse -> chunk -> (enrich neu .env bat) -> embed -> store.
Enrich/embedding theo cau hinh .env (INDEX_STEPS, ENRICH_*, EMBEDDING_MODEL).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

# Cho phep `import app.*` khi chay tu goc du an.
_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
sys.path.insert(0, str(_BACKEND))

SEED_DIR = _ROOT / "data" / "seed"

# Metadata cho tung file seed. SUA lai neu can (soHieu + tenVanBan la quan trong nhat;
# cac ngay chi la metadata, co the chinh cho dung).
SEED_META: dict[str, dict] = {
    "36_2024_QH15_444251.pdf": dict(
        soHieu="36/2024/QH15",
        tenVanBan="Luat Trat tu, an toan giao thong duong bo",
        ngayBanHanh=date(2024, 6, 27), ngayHieuLuc=date(2025, 1, 1),
        coQuanBanHanh="Quoc hoi", loaiVanBan="Luat",
    ),
    "35_2024_QH15_588811.pdf": dict(
        soHieu="35/2024/QH15",
        tenVanBan="Luat Duong bo",
        ngayBanHanh=date(2024, 6, 27), ngayHieuLuc=date(2025, 1, 1),
        coQuanBanHanh="Quoc hoi", loaiVanBan="Luat",
    ),
    "38_2024_TT-BGTVT_622477.pdf": dict(
        soHieu="38/2024/TT-BGTVT",
        tenVanBan="Thong tu 38/2024/TT-BGTVT",
        ngayBanHanh=date(2024, 11, 15), ngayHieuLuc=date(2025, 1, 1),
        coQuanBanHanh="Bo Giao thong van tai", loaiVanBan="Thong tu",
    ),
    "168_2024_ND-CP_619502.pdf": dict(
        soHieu="168/2024/ND-CP",
        tenVanBan="Nghi dinh 168/2024/ND-CP xu phat vi pham hanh chinh ve TTATGT duong bo",
        ngayBanHanh=date(2024, 12, 26), ngayHieuLuc=date(2025, 1, 1),
        coQuanBanHanh="Chinh phu", loaiVanBan="Nghi dinh",
    ),
}


def _list_dry_run() -> None:
    print(f"Seed dir: {SEED_DIR}")
    for filename, meta in SEED_META.items():
        mark = "[co]" if (SEED_DIR / filename).exists() else "[THIEU]"
        print(f"  {mark} {filename}  ->  {meta['soHieu']} | {meta['tenVanBan']}")


async def _seed(replace: bool, reset: bool, only: str = "", enrich: str = "none") -> None:
    import chromadb

    from app.config import get_settings
    from app.indexing.base import IndexDeps
    from app.logging_config import setup_logging
    from app.models.schemas import DocumentMetadataInput
    from app.pipelines.document_pipeline import DocumentPipeline, DuplicateDocumentError
    from app.providers.huggingface_embedding import HuggingFaceEmbedding
    from app.providers.llm_factory import create_primary_llm
    from app.storage.vector_store import VectorStore

    settings = get_settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file or None)

    embedding = HuggingFaceEmbedding(model_name=settings.embedding_model)
    primary_llm = create_primary_llm(settings)
    chroma = chromadb.PersistentClient(path=settings.chroma_persist_path)

    if reset:
        try:
            chroma.delete_collection(settings.chroma_collection_name)
            print("Da xoa collection cu (--reset).")
        except Exception:
            pass  # chua ton tai thi bo qua

    store = VectorStore(chroma, settings.chroma_collection_name)
    index_deps = IndexDeps(settings=settings, primary_llm=primary_llm, embedding=embedding)

    # Chon enrich theo flag --enrich (KHONG con doc INDEX_STEPS/ENRICH_SOURCE tu .env).
    #   none = khong enrich; auto = LLM (ENRICH_LLM_* trong .env); file = doc ENRICH_FILE.
    enrich = (enrich or "none").strip().lower()
    index_steps = []
    enrich_desc = "none"
    if enrich == "auto":
        from app.indexing.enrich_step import build_auto
        index_steps = [build_auto(index_deps)]
        enrich_desc = "auto (LLM)"
    elif enrich == "file":
        from app.indexing.enrich_io import get_enrich_file_path
        from app.indexing.enrich_step import _EnrichFileIndex, EnrichStep
        path = get_enrich_file_path()
        if not path.is_file():
            raise SystemExit(f"[LOI] --enrich file nhung khong thay {path}")
        index_steps = [EnrichStep(model="file (manual)", file_index=_EnrichFileIndex(path))]
        enrich_desc = f"file ({path.name})"
    elif enrich != "none":
        raise SystemExit(f"[LOI] --enrich '{enrich}' khong hop le (none|auto|file).")

    pipeline = DocumentPipeline(embedding, store, index_steps=index_steps)

    print(f"ChromaDB   : {settings.chroma_persist_path}")
    print(f"Embedding  : {settings.embedding_model}")
    print(f"Enrich     : {enrich_desc}")
    print("-" * 60)

    ok = skip = fail = 0
    for filename, meta in SEED_META.items():
        if only and only.lower() not in filename.lower():
            continue  # --only: chi nap file co ten chua chuoi nay
        path = SEED_DIR / filename
        if not path.exists():
            print(f"[THIEU] khong thay file: {filename}")
            skip += 1
            continue
        md = DocumentMetadataInput(**meta)
        try:
            res = await pipeline.process_document(
                path.read_bytes(), filename, md, replace=replace
            )
            print(f"[OK]    {md.soHieu}: {res.soChunks} chunk")
            ok += 1
        except DuplicateDocumentError:
            print(f"[TRUNG] {md.soHieu} da ton tai — dung --replace de ghi de, hoac --reset")
            skip += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[LOI]   {md.soHieu}: {type(exc).__name__}: {exc}")
            fail += 1

    print("-" * 60)
    print(f"Tong ket: {ok} OK, {skip} bo qua/trung, {fail} loi | tong chunk trong DB: {store.count()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed du lieu luat vao ChromaDB (khong can UI).")
    ap.add_argument("--replace", action="store_true", help="Ghi de van ban da ton tai (cung soHieu).")
    ap.add_argument("--reset", action="store_true", help="Xoa sach collection roi nap lai tu dau.")
    ap.add_argument("--dry-run", action="store_true", help="Chi liet ke file se nap, khong xu ly.")
    ap.add_argument("--only", default="", help="Chi nap file co ten chua chuoi nay (vd: 168).")
    ap.add_argument(
        "--enrich", default="none", choices=["none", "auto", "file"],
        help="Enrich: none (khong) | auto (LLM) | file (doc ENRICH_FILE trong .env).",
    )
    args = ap.parse_args()

    if args.dry_run:
        _list_dry_run()
        return
    asyncio.run(_seed(replace=args.replace, reset=args.reset, only=args.only, enrich=args.enrich))


if __name__ == "__main__":
    main()
