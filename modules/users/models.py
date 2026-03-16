import datetime as dt

from sqlalchemy import TIMESTAMP, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.base import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=dt.datetime.utcnow, nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
        nullable=False,
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=dt.datetime.utcnow,
        onupdate=dt.datetime.utcnow,
        nullable=False,
    )
