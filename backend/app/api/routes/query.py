"""API route: POST /api/query — tra cứu luật giao thông."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_query_pipeline
from app.models.schemas import KetQuaTraLoi, QueryRequest
from app.pipelines.query_pipeline import QueryPipeline

router = APIRouter(prefix="/api", tags=["query"])


@router.post("/query", response_model=KetQuaTraLoi)
async def query(
    request: QueryRequest,
    pipeline: QueryPipeline = Depends(get_query_pipeline),
) -> KetQuaTraLoi:
    """Tra cứu luật giao thông."""
    return await pipeline.process_query(request.cauHoi)
