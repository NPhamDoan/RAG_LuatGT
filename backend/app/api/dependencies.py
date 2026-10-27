"""DI container — hold singleton instances."""

from typing import Any

from app.pipelines.document_pipeline import DocumentPipeline
from app.pipelines.query_pipeline import QueryPipeline
from app.storage.vector_store import VectorStore

_query_pipeline: QueryPipeline | None = None
_document_pipeline: DocumentPipeline | None = None
_vector_store: VectorStore | None = None
# IndexDeps dùng để dựng index step động (vd enrich auto) theo lựa chọn trên form.
_index_deps: Any = None


def set_index_deps(deps: Any) -> None:
    global _index_deps
    _index_deps = deps


def get_index_deps() -> Any:
    return _index_deps


def set_query_pipeline(pipeline: QueryPipeline) -> None:
    global _query_pipeline
    _query_pipeline = pipeline


def set_document_pipeline(pipeline: DocumentPipeline) -> None:
    global _document_pipeline
    _document_pipeline = pipeline


def set_vector_store(store: VectorStore) -> None:
    global _vector_store
    _vector_store = store


def get_query_pipeline() -> QueryPipeline:
    assert _query_pipeline is not None, "QueryPipeline chưa được khởi tạo"
    return _query_pipeline


def get_document_pipeline() -> DocumentPipeline:
    assert _document_pipeline is not None, "DocumentPipeline chưa được khởi tạo"
    return _document_pipeline


def get_vector_store() -> VectorStore:
    assert _vector_store is not None, "VectorStore chưa được khởi tạo"
    return _vector_store
