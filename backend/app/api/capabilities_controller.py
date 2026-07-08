"""Capability discovery: which optional modules and specialists are active.

The frontend gates feature routes on this instead of rebuilding per
environment; operators use it to verify configuration after a deploy.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.chat.registry import SPECIALISTS, get_enabled_specs
from app.core.config import Settings
from app.core.deps import get_settings
from app.modules import ALL_MODULES, active_modules

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


class ModuleInfo(BaseModel):
    name: str
    title: str
    description: str
    active: bool


class SpecialistInfo(BaseModel):
    key: str
    enabled: bool


class CapabilitiesResponse(BaseModel):
    modules: list[ModuleInfo]
    specialists: list[SpecialistInfo]


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CapabilitiesResponse:
    active = {m.name for m in active_modules(settings)}
    enabled_keys = {s.key for s in get_enabled_specs(settings)}
    module_specialists = [
        (m.specialist, m.name in active)
        for m in ALL_MODULES
        if m.specialist is not None
    ]
    return CapabilitiesResponse(
        modules=[
            ModuleInfo(
                name=m.name,
                title=m.title,
                description=m.description,
                active=m.name in active,
            )
            for m in ALL_MODULES
        ],
        specialists=[
            SpecialistInfo(key=s.key, enabled=s.key in enabled_keys)
            for s in SPECIALISTS
        ]
        + [
            SpecialistInfo(key=spec.key, enabled=is_active)
            for spec, is_active in module_specialists
        ],
    )
