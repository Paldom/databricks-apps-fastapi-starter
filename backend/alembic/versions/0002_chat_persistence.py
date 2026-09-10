"""Persisted chat turns, Genie conversation handle.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "parts",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column("messages", sa.Column("trace_id", sa.String(64), nullable=True))
    op.create_index(
        "ix_messages_session_created_id", "messages", ["session_id", "created_at", "id"]
    )
    op.add_column(
        "chat_sessions",
        sa.Column("genie_conversation_id", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_sessions", "genie_conversation_id")
    op.drop_index("ix_messages_session_created_id", table_name="messages")
    op.drop_column("messages", "trace_id")
    op.drop_column("messages", "parts")
