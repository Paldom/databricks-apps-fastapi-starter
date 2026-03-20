from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, TIMESTAMP, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        default=lambda: f"proj-{uuid.uuid4().hex[:12]}",
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("users.id"), nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[str] = mapped_column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_projects_owner_user_id", "owner_user_id"),
    )
