"""add_abandoned_cart_journeys_and_offers

Add persistence for abandoned cart tracking and recovery offers.

Revision ID: d4e5f6a7b8c9
Revises: c9e0f1a2b3c4
Create Date: 2026-03-14 02:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "abandoned_cart_journeys",
        sa.Column("cart_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_id", sa.String(length=36), nullable=True),
        sa.Column("merchant_name", sa.String(length=100), nullable=True),
        sa.Column("cart_value", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="VND"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "restaurant_open",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "items_available",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("deep_link", sa.Text(), nullable=True),
        sa.Column("payload_snapshot", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_webhook_error", sa.Text(), nullable=True),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovery_order_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_abandoned_cart_journeys")),
        sa.UniqueConstraint("cart_id", name=op.f("uq_abandoned_cart_journeys_cart_id")),
    )
    op.create_index(
        op.f("ix_abandoned_cart_journeys_user_id"),
        "abandoned_cart_journeys",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_abandoned_cart_journeys_merchant_id"),
        "abandoned_cart_journeys",
        ["merchant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_abandoned_cart_journeys_status"),
        "abandoned_cart_journeys",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_abandoned_cart_journeys_last_activity_at"),
        "abandoned_cart_journeys",
        ["last_activity_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_abandoned_cart_journeys_recovery_order_id"),
        "abandoned_cart_journeys",
        ["recovery_order_id"],
        unique=False,
    )

    op.create_table(
        "journey_offers",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("journey_type", sa.String(length=50), nullable=False),
        sa.Column("source_cart_id", sa.String(length=64), nullable=False),
        sa.Column("offer_type", sa.String(length=30), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("max_discount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("min_cart_value", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
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
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journey_offers")),
        sa.UniqueConstraint("code", name=op.f("uq_journey_offers_code")),
    )
    op.create_index(op.f("ix_journey_offers_user_id"), "journey_offers", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_journey_offers_journey_type"),
        "journey_offers",
        ["journey_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journey_offers_source_cart_id"),
        "journey_offers",
        ["source_cart_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_journey_offers_offer_type"),
        "journey_offers",
        ["offer_type"],
        unique=False,
    )
    op.create_index(op.f("ix_journey_offers_status"), "journey_offers", ["status"], unique=False)
    op.create_index(
        op.f("ix_journey_offers_expires_at"),
        "journey_offers",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_journey_offers_expires_at"), table_name="journey_offers")
    op.drop_index(op.f("ix_journey_offers_status"), table_name="journey_offers")
    op.drop_index(op.f("ix_journey_offers_offer_type"), table_name="journey_offers")
    op.drop_index(op.f("ix_journey_offers_source_cart_id"), table_name="journey_offers")
    op.drop_index(op.f("ix_journey_offers_journey_type"), table_name="journey_offers")
    op.drop_index(op.f("ix_journey_offers_user_id"), table_name="journey_offers")
    op.drop_table("journey_offers")

    op.drop_index(
        op.f("ix_abandoned_cart_journeys_recovery_order_id"),
        table_name="abandoned_cart_journeys",
    )
    op.drop_index(
        op.f("ix_abandoned_cart_journeys_last_activity_at"),
        table_name="abandoned_cart_journeys",
    )
    op.drop_index(op.f("ix_abandoned_cart_journeys_status"), table_name="abandoned_cart_journeys")
    op.drop_index(
        op.f("ix_abandoned_cart_journeys_merchant_id"),
        table_name="abandoned_cart_journeys",
    )
    op.drop_index(op.f("ix_abandoned_cart_journeys_user_id"), table_name="abandoned_cart_journeys")
    op.drop_table("abandoned_cart_journeys")
