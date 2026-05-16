from fastapi import APIRouter

from app.api.routes import v1, v2, v3

api_router = APIRouter()
api_router.include_router(v1.router, prefix="/v1", tags=["v1"])
api_router.include_router(v2.router, prefix="/v2", tags=["v2"])
api_router.include_router(v3.router, prefix="/v3", tags=["v3"])
