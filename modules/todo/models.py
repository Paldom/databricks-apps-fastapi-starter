import uuid
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from modules.base import Base, AuditMixin


class Todo(AuditMixin, Base):
    __tablename__ = "todo"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
