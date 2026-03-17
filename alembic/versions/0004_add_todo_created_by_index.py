"""add index on todo.created_by

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-17 00:00:01
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_todo_created_by", "todo", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_todo_created_by", table_name="todo")
