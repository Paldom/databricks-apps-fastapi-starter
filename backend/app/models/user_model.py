import datetime as dt

from sqlalchemy import TIMESTAMP, Boolean, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AppUser(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_username: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=func.now(), server_default=func.now()
    )
    # Ownership columns are nullable for the users table since users
    # don't have an "owner" in the same sense as domain entities.
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
