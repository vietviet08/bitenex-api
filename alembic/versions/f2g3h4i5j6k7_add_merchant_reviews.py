"""add merchant_reviews and review_summary_cache tables

Revision ID: f2g3h4i5j6k7
Revises: e1f2a3b4c5d6
Create Date: 2026-05-08 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2g3h4i5j6k7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================================
    # merchant_reviews table
    # =========================================================================
    op.create_table(
        "merchant_reviews",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), nullable=True, index=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("reviewer_name", sa.String(100), nullable=True),
        sa.Column("reviewer_avatar", sa.Text(), nullable=True),
        # Soft delete + timestamps (BaseModel)
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_merchant_reviews_merchant_rating",
        "merchant_reviews",
        ["merchant_id", "rating"],
    )

    # =========================================================================
    # merchant_review_summary_cache table
    # =========================================================================
    op.create_table(
        "merchant_review_summary_cache",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("merchant_id", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column("pros_json", sa.Text(), nullable=True),
        sa.Column("cons_json", sa.Text(), nullable=True),
        sa.Column("overall_sentiment", sa.String(20), nullable=True),
        sa.Column("summary_vi", sa.Text(), nullable=True),
        sa.Column("total_reviews_analyzed", sa.Integer(), default=0, nullable=False),
        sa.Column("average_rating_snapshot", sa.Float(), nullable=True),
        sa.Column("is_valid", sa.Boolean(), default=True, nullable=False),
        # BaseModel timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), default=False, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("merchant_review_summary_cache")
    op.drop_index("ix_merchant_reviews_merchant_rating", table_name="merchant_reviews")
    op.drop_table("merchant_reviews")
