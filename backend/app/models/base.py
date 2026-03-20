"""Backward-compatible re-exports from :mod:`app.core.db.base`."""

from app.core.db.base import AuditMixin, Base, TimestampMixin

__all__ = ["AuditMixin", "Base", "TimestampMixin"]
