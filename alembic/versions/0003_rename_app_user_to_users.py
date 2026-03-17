"""rename app_user to users and normalize columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17 00:00:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.rename_table("app_user", "users")
    op.alter_column("users", "name", new_column_name="display_name")
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column("created_by", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("updated_by", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "updated_by")
    op.drop_column("users", "created_by")
    op.drop_column("users", "is_active")
    op.alter_column("users", "display_name", new_column_name="name")
    op.rename_table("users", "app_user")
