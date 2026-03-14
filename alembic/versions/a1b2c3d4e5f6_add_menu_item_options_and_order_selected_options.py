"""add_menu_item_options_and_order_selected_options

Creates option group and option tables for menu item customization,
and adds selected_options column to order_items for snapshotting
customer selections at order time.

- menu_item_option_groups (option groups per menu item)
- menu_item_options (individual options per group)
- order_items.selected_options (JSON text column)

Revision ID: a1b2c3d4e5f6
Revises: 830c7d77debf
Create Date: 2026-02-14 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "830c7d77debf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create menu_item_option_groups table
    op.create_table(
        "menu_item_option_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "menu_item_id",
            sa.String(36),
            sa.ForeignKey("menu_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "selection_type", sa.String(20), nullable=False, server_default="single"
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    # Create menu_item_options table
    op.create_table(
        "menu_item_options",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "option_group_id",
            sa.String(36),
            sa.ForeignKey("menu_item_option_groups.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("price_delta", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "is_available", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
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
    )

    # Add selected_options column to order_items
    op.add_column(
        "order_items",
        sa.Column("selected_options", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_items", "selected_options")
    op.drop_table("menu_item_options")
    op.drop_table("menu_item_option_groups")
