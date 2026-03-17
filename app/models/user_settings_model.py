from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    owner_user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id"), primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notifications: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true",
    )
    updated_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )
