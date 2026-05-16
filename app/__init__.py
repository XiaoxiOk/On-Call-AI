from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.schemas.common import HealthResponse
from app.services.runtime import build_application_services


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.settings = settings
        application.state.services = build_application_services(settings)
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        summary="Backend API for the On-Call assistant web application.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=settings.cors_allow_methods,
        allow_headers=["*"],
    )

    @application.get("/health", tags=["system"], response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        return HealthResponse(status="ok")

    application.include_router(api_router)
    return application
