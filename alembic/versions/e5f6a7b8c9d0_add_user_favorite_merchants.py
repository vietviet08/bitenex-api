"""add user favorite merchants

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c4
Create Date: 2026-06-03 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_favorite_merchants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("merchant_id", sa.String(36), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "merchant_id", name="uq_user_favorite_merchant"),
    )
    op.create_index(
        "ix_user_favorite_merchants_user_id",
        "user_favorite_merchants",
        ["user_id"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "ix_user_favorite_merchants_merchant_id",
        "user_favorite_merchants",
        ["merchant_id"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_favorite_merchants_merchant_id", table_name="user_favorite_merchants"
    )
    op.drop_index(
        "ix_user_favorite_merchants_user_id", table_name="user_favorite_merchants"
    )
    op.drop_table("user_favorite_merchants")
