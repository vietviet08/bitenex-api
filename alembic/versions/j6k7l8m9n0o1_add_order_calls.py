"""add order calls

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-05-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "order_calls",
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("caller_user_id", sa.String(length=36), nullable=False),
        sa.Column("callee_user_id", sa.String(length=36), nullable=False),
        sa.Column("caller_role", sa.String(length=20), nullable=False),
        sa.Column("callee_role", sa.String(length=20), nullable=False),
        sa.Column("channel_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_by", sa.String(length=36), nullable=True),
        sa.Column("end_reason", sa.String(length=80), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_order_calls_order_id_orders"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_calls")),
        sa.UniqueConstraint("channel_name", name=op.f("uq_order_calls_channel_name")),
    )
    op.create_index(op.f("ix_order_calls_order_id"), "order_calls", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_calls_caller_user_id"), "order_calls", ["caller_user_id"], unique=False)
    op.create_index(op.f("ix_order_calls_callee_user_id"), "order_calls", ["callee_user_id"], unique=False)
    op.create_index(op.f("ix_order_calls_status"), "order_calls", ["status"], unique=False)
    op.create_index(op.f("ix_order_calls_expires_at"), "order_calls", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_calls_expires_at"), table_name="order_calls")
    op.drop_index(op.f("ix_order_calls_status"), table_name="order_calls")
    op.drop_index(op.f("ix_order_calls_callee_user_id"), table_name="order_calls")
    op.drop_index(op.f("ix_order_calls_caller_user_id"), table_name="order_calls")
    op.drop_index(op.f("ix_order_calls_order_id"), table_name="order_calls")
    op.drop_table("order_calls")
