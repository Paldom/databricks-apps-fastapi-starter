import datetime as dt

from sqlalchemy import TIMESTAMP, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_username: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP, default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP,
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP, default=func.now(), server_default=func.now()
    )
