"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("preferred_username", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    # ── projects ───────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("owner_user_id", sa.String(255), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])

    # ── user_settings ──────────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("owner_user_id", sa.String(255), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notifications", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # ── chat_sessions ──────────────────────────────────────────────
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("project_id", sa.String(255), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])
    op.create_index("ix_chat_sessions_project_id", "chat_sessions", ["project_id"])

    # ── messages ───────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_user_id", "messages", ["user_id"])
    op.create_index("ix_messages_session_created", "messages", ["session_id", "created_at"])

    # ── file_records ───────────────────────────────────────────────
    op.create_table(
        "file_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.String(255), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.String(255), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(50), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
    )
    op.create_index("ix_file_records_user_id", "file_records", ["user_id"])
    op.create_index("ix_file_records_session_id", "file_records", ["session_id"])
    op.create_index("ix_file_records_project_id", "file_records", ["project_id"])


def downgrade() -> None:
    op.drop_table("file_records")
    op.drop_table("messages")
    op.drop_table("chat_sessions")
    op.drop_table("user_settings")
    op.drop_table("projects")
    op.drop_table("users")
