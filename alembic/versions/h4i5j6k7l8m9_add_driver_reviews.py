"""add driver_reviews table

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-05-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, None] = "g3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "driver_reviews",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("driver_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), nullable=False, index=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("tip_amount", sa.Float(), server_default="0", nullable=False),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("reviewer_avatar", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_driver_reviews_driver_rating", "driver_reviews", ["driver_id", "rating"])
    op.create_index("uq_driver_reviews_order_user", "driver_reviews", ["order_id", "user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_driver_reviews_order_user", table_name="driver_reviews")
    op.drop_index("ix_driver_reviews_driver_rating", table_name="driver_reviews")
    op.drop_table("driver_reviews")
