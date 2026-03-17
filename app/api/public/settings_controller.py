from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import ConfigDict

from app.api.public.common.schemas import ApiModel
from app.core.deps import get_user_settings_service
from app.services.user_settings_service import UserSettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


class UserSettings(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "john@example.com",
                "notifications": True,
            }
        }
    )

    name: str
    email: str
    notifications: bool


@router.get(
    "",
    operation_id="getUserSettings",
    response_model=UserSettings,
)
async def get_user_settings(
    service: UserSettingsService = Depends(get_user_settings_service),
) -> UserSettings:
    result = await service.get_settings()
    return UserSettings(**result)


@router.put(
    "",
    operation_id="updateUserSettings",
    response_model=UserSettings,
)
async def update_user_settings(
    body: UserSettings,
    service: UserSettingsService = Depends(get_user_settings_service),
) -> UserSettings:
    result = await service.update_settings(
        name=body.name, email=body.email, notifications=body.notifications,
    )
    return UserSettings(**result)
