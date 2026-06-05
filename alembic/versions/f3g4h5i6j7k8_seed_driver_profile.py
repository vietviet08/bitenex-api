"""seed driver profile

Revision ID: f3g4h5i6j7k8
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3g4h5i6j7k8"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO drivers (
            id,
            user_id,
            status,
            is_approved,
            vehicle_type,
            vehicle_plate,
            vehicle_model,
            license_number,
            total_deliveries,
            average_rating,
            is_deleted
        )
        VALUES (
            '90000000-0000-0000-0000-000000000001',
            '10000000-0000-0000-0000-000000000005',
            'ONLINE',
            TRUE,
            'Motorcycle',
            '59-A3 123.45',
            'Honda Wave Alpha',
            'A1-987654321',
            15,
            4.9,
            FALSE
        )
        ON CONFLICT (user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM drivers WHERE id = '90000000-0000-0000-0000-000000000001'")
