"""create app_user table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-16 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("preferred_username", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

def downgrade() -> None:
    op.drop_table("app_user")
