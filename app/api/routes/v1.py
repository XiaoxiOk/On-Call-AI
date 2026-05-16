from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas.common import PhaseStatusResponse
from app.schemas.search import SearchResponse
from app.dependencies import get_services
from app.services.runtime import ApplicationServices
from app.utils.text import collapse_whitespace

router = APIRouter()


@router.get("", response_model=PhaseStatusResponse, summary="Phase 1 placeholder")
async def phase_one_root() -> PhaseStatusResponse:
    return PhaseStatusResponse(
        phase="v1",
        message="Phase 1 keyword search is available at GET /v1/search?q=...",
    )


@router.get("/search", response_model=SearchResponse, summary="BM25 keyword search")
async def search_documents(
    q: str = Query(..., description="Keyword query"),
    services: ApplicationServices = Depends(get_services),
) -> SearchResponse:
    query = collapse_whitespace(q)
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    results = services.keyword_search.search(query)
    return SearchResponse(query=query, results=results)
