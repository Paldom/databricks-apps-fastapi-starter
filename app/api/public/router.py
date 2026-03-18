from __future__ import annotations

from fastapi import APIRouter

from app.api.public.health_controller import router as health_router
from app.api.public.me_controller import router as me_router
from app.api.public.dashboard_controller import router as dashboard_router
from app.api.public.projects_controller import router as projects_router
from app.api.public.chats_controller import router as chats_router
from app.api.public.documents_controller import router as documents_router
from app.api.public.settings_controller import router as settings_router
from app.api.public.chat_stream_controller import router as chat_stream_router
from app.api.public.stream_controller import router as stream_router


def build_api_router() -> APIRouter:
    """Build the frontend-facing API router matching the canonical OpenAPI contract."""
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(me_router)
    router.include_router(dashboard_router)
    router.include_router(projects_router)
    router.include_router(chats_router)
    router.include_router(documents_router)
    router.include_router(settings_router)
    router.include_router(chat_stream_router)
    router.include_router(stream_router)
    return router
