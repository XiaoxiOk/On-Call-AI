from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_services
from app.schemas.common import PhaseStatusResponse
from app.schemas.search import SearchResponse
from app.services.runtime import ApplicationServices
from app.services.search import SemanticSearchUnavailableError
from app.utils.text import collapse_whitespace

router = APIRouter()


@router.get("", response_model=PhaseStatusResponse, summary="Phase 2 placeholder")
async def phase_two_root() -> PhaseStatusResponse:
    return PhaseStatusResponse(
        phase="v2",
        message="Phase 2 semantic search is available at GET /v2/search?q=...",
    )


@router.get("/search", response_model=SearchResponse, summary="Semantic vector search")
async def search_documents(
    q: str = Query(..., description="Semantic query"),
    services: ApplicationServices = Depends(get_services),
) -> SearchResponse:
    query = collapse_whitespace(q)
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        results = services.semantic_search.search(query)
    except SemanticSearchUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return SearchResponse(query=query, results=results)
