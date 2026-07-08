from __future__ import annotations

from fastapi import APIRouter

from app.api.agents_controller import router as agents_router
from app.api.capabilities_controller import router as capabilities_router
from app.api.chat_stream_controller import router as chat_stream_router
from app.api.chats_controller import router as chats_router
from app.api.documents_controller import router as documents_router
from app.api.health_controller import router as health_router
from app.api.knowledge_controller import router as knowledge_router
from app.api.me_controller import router as me_router
from app.api.projects_controller import router as projects_router
from app.api.settings_controller import router as settings_router
from app.core.config import Settings
from app.modules import active_modules


def build_api_router(settings: Settings) -> APIRouter:
    router = APIRouter()
    router.include_router(health_router)
    router.include_router(capabilities_router)
    router.include_router(me_router)
    router.include_router(projects_router)
    router.include_router(chats_router)
    router.include_router(documents_router)
    router.include_router(knowledge_router)
    router.include_router(settings_router)
    router.include_router(chat_stream_router)
    router.include_router(agents_router)

    # Optional modules mount only when configured (see DESIGN.md).
    for module in active_modules(settings):
        if module.router is not None:
            router.include_router(module.router)
    return router
