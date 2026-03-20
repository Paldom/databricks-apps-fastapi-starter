from __future__ import annotations

from app.repositories.user_settings_repository import UserSettingsRepository


class UserSettingsService:
    def __init__(
        self, repo: UserSettingsRepository, user_id: str,
        default_name: str, default_email: str | None,
    ) -> None:
        self._repo = repo
        self._user_id = user_id
        self._default_name = default_name
        self._default_email = default_email

    async def get_settings(self) -> dict:
        settings = await self._repo.get_or_create(
            self._user_id, self._default_name, self._default_email,
        )
        return {
            "name": settings.name,
            "email": settings.email or "",
            "notifications": settings.notifications,
        }

    async def update_settings(
        self, name: str, email: str, notifications: bool,
    ) -> dict:
        settings = await self._repo.update_settings(
            self._user_id, name, email, notifications,
        )
        return {
            "name": settings.name,
            "email": settings.email or "",
            "notifications": settings.notifications,
        }
