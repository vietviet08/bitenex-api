
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4f2b8bb3e12d"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOW_UTC = sa.text("timezone('utc', now())")


def upgrade() -> None:
    op.create_table(
        "vouchers",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("merchant_id", sa.String(length=36), nullable=True),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("discount_value", sa.Float(), nullable=False),
        sa.Column("max_discount_amount", sa.Float(), nullable=True),
        sa.Column("min_order_amount", sa.Float(), nullable=False),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False),
        sa.Column("per_user_limit", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW_UTC, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=NOW_UTC, nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vouchers")),
        sa.UniqueConstraint("code", name=op.f("uq_vouchers_code")),
    )
    op.create_index(op.f("ix_vouchers_code"), "vouchers", ["code"], unique=True)
    op.create_index(op.f("ix_vouchers_is_active"), "vouchers", ["is_active"], unique=False)
    op.create_index(op.f("ix_vouchers_merchant_id"), "vouchers", ["merchant_id"], unique=False)

    op.add_column("orders", sa.Column("voucher_id", sa.String(length=36), nullable=True))
    op.add_column("orders", sa.Column("voucher_code", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_orders_voucher_code"), "orders", ["voucher_code"], unique=False)
    op.create_index(op.f("ix_orders_voucher_id"), "orders", ["voucher_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_voucher_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_voucher_code"), table_name="orders")
    op.drop_column("orders", "voucher_code")
    op.drop_column("orders", "voucher_id")

    op.drop_index(op.f("ix_vouchers_merchant_id"), table_name="vouchers")
    op.drop_index(op.f("ix_vouchers_is_active"), table_name="vouchers")
    op.drop_index(op.f("ix_vouchers_code"), table_name="vouchers")
    op.drop_table("vouchers")
