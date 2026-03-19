from __future__ import annotations

from fastapi import APIRouter

from app.api.chats_controller import router as chats_router
from app.api.chat_stream_controller import router as chat_stream_router
from app.api.documents_controller import router as documents_router
from app.api.examples_controller import router as examples_router
from app.api.health_controller import router as health_router
from app.api.me_controller import router as me_router
from app.api.projects_controller import router as projects_router
from app.api.settings_controller import router as settings_router


def build_api_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(me_router)
    router.include_router(examples_router)
    router.include_router(projects_router)
    router.include_router(chats_router)
    router.include_router(documents_router)
    router.include_router(settings_router)
    router.include_router(chat_stream_router)
    return router
