from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_settings_model import UserSettings


class UserSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(
        self, owner_user_id: str, default_name: str, default_email: str | None,
    ) -> UserSettings:
        result = await self._session.execute(
            select(UserSettings).where(
                UserSettings.owner_user_id == owner_user_id,
            )
        )
        settings = result.scalar_one_or_none()
        if settings is not None:
            return settings

        settings = UserSettings(
            owner_user_id=owner_user_id,
            name=default_name,
            email=default_email,
            notifications=True,
        )
        self._session.add(settings)
        await self._session.flush()
        return settings

    async def update_settings(
        self,
        owner_user_id: str,
        name: str,
        email: str,
        notifications: bool,
    ) -> UserSettings:
        result = await self._session.execute(
            select(UserSettings).where(
                UserSettings.owner_user_id == owner_user_id,
            )
        )
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(
                owner_user_id=owner_user_id,
                name=name,
                email=email,
                notifications=notifications,
            )
            self._session.add(settings)
        else:
            settings.name = name
            settings.email = email
            settings.notifications = notifications
        await self._session.flush()
        return settings
