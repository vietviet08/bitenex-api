"""add order chat messages

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-05-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_type", sa.String(length=30), nullable=False),
        sa.Column("sender_user_id", sa.String(length=36), nullable=False),
        sa.Column("sender_role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
    )
    op.create_index(op.f("ix_chat_messages_order_id"), "chat_messages", ["order_id"], unique=False)
    op.create_index(
        "ix_chat_messages_order_conversation_created",
        "chat_messages",
        ["order_id", "conversation_type", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_messages_conversation_type"),
        "chat_messages",
        ["conversation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chat_messages_sender_user_id"),
        "chat_messages",
        ["sender_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_chat_messages_sender_role"), "chat_messages", ["sender_role"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_messages_sender_role"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_sender_user_id"), table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_conversation_type"), table_name="chat_messages")
    op.drop_index("ix_chat_messages_order_conversation_created", table_name="chat_messages")
    op.drop_index(op.f("ix_chat_messages_order_id"), table_name="chat_messages")
    op.drop_table("chat_messages")
