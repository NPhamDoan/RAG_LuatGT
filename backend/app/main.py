"""FastAPI application — RAG Luật Giao Thông."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

import chromadb
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import (
    set_document_pipeline,
    set_index_deps,
    set_query_pipeline,
    set_vector_store,
)
from app.api.routes.auth import router as auth_router
from app.api.routes.documents import router as documents_router
from app.api.routes.query import router as query_router
from app.config import get_settings
from app.logging_config import setup_logging
from app.indexing.base import IndexDeps, load_index_steps
from app.pipelines.document_pipeline import DocumentPipeline
from app.pipelines.query_pipeline import QueryPipeline
from app.pipelines.steps.base import StepDeps, load_steps
from app.providers.huggingface_embedding import HuggingFaceEmbedding
from app.providers.llm_factory import create_primary_llm
from app.retrieval.base import load_strategy
from app.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Khởi tạo providers + pipelines khi startup."""
    settings = get_settings()

    logger.info("Khởi tạo embedding provider (%s)...", settings.embedding_model)
    embedding = HuggingFaceEmbedding(model_name=settings.embedding_model)

    primary_llm = create_primary_llm(settings)

    logger.info("Khởi tạo ChromaDB tại: %s", settings.chroma_persist_path)
    chroma_client = chromadb.PersistentClient(path=settings.chroma_persist_path)
    vector_store = VectorStore(chroma_client, settings.chroma_collection_name)

    # Kiến trúc module: chọn retrieval strategy + nạp query steps theo config.
    logger.info("Retrieval strategy: %s", settings.retrieval_strategy)
    retrieval = load_strategy(settings.retrieval_strategy, vector_store)
    step_deps = StepDeps(
        settings=settings, primary_llm=primary_llm, embedding=embedding, store=vector_store
    )
    steps = load_steps(settings.query_steps_list, step_deps)

    index_deps = IndexDeps(settings=settings, primary_llm=primary_llm, embedding=embedding)
    index_steps = load_index_steps(settings.index_steps_list, index_deps)

    document_pipeline = DocumentPipeline(embedding, vector_store, index_steps=index_steps)
    query_pipeline = QueryPipeline(primary_llm, embedding, retrieval, settings, steps)

    set_vector_store(vector_store)
    set_document_pipeline(document_pipeline)
    set_query_pipeline(query_pipeline)
    set_index_deps(index_deps)  # để route dựng enrich step động theo form (auto)

    logger.info("App sẵn sàng.")
    yield
    logger.info("App đang tắt.")


def create_app() -> FastAPI:
    """Tạo và cấu hình FastAPI app."""
    settings = get_settings()
    setup_logging(level=settings.log_level, log_file=settings.log_file or None)

    app = FastAPI(
        title="RAG Luật Giao Thông API",
        description="Hệ thống RAG tra cứu luật giao thông Việt Nam",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        correlation_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        logger.info("→ %s %s", request.method, request.url.path)
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info("← %s %s %d (%.0fms) [%s]", request.method, request.url.path, response.status_code, ms, correlation_id)
        return response

    # Routes
    app.include_router(auth_router)
    app.include_router(query_router)
    app.include_router(documents_router)

    if not settings.admin_password_hash:
        logger.warning(
            "AUTH TAT: ADMIN_PASSWORD_HASH trong -> route ghi (/api/documents POST/PATCH/DELETE) "
            "MO cong khai. Dat ADMIN_PASSWORD_HASH trong .env de bat bao ve."
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
