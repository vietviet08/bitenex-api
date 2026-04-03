"""seed user driver admin accounts

Revision ID: 334718eb712d
Revises: d4e5f6a7b8c9
Create Date: 2026-04-03 15:35:35.207580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '334718eb712d'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PASSWORD_HASH = "$2b$12$4Tm8dlw.PKKsJmcDAeN8xOPQPOI/zpa5H4De2BoAicyCRtEWsB8f6"  # password123

USER_IDS = (
    "10000000-0000-0000-0000-000000000004",  # User
    "10000000-0000-0000-0000-000000000005",  # Driver
    "10000000-0000-0000-0000-000000000006",  # Admin
)

users_table = sa.table(
    "users",
    sa.column("id", sa.String(length=36)),
    sa.column("email", sa.String(length=255)),
    sa.column("password_hash", sa.String(length=255)),
    sa.column("full_name", sa.String(length=100)),
    sa.column("phone", sa.String(length=20)),
    sa.column("avatar_url", sa.Text()),
    sa.column("role", sa.String(length=20)),
    sa.column("is_active", sa.Boolean()),
    sa.column("is_verified", sa.Boolean()),
    sa.column("is_deleted", sa.Boolean()),
)

def upgrade() -> None:
    """Upgrade schema."""
    op.bulk_insert(
        users_table,
        [
            {
                "id": USER_IDS[0],
                "email": "user@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "Test User",
                "phone": "0902000001",
                "avatar_url": "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?auto=format&fit=crop&w=256&q=80",
                "role": "USER",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
            {
                "id": USER_IDS[1],
                "email": "driver@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "Test Driver",
                "phone": "0902000002",
                "avatar_url": "https://images.unsplash.com/photo-1633332755192-727a05c4013d?auto=format&fit=crop&w=256&q=80",
                "role": "DRIVER",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
            {
                "id": USER_IDS[2],
                "email": "admin@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "System Admin",
                "phone": "0902000003",
                "avatar_url": "https://images.unsplash.com/photo-1599566150163-29194dcaad36?auto=format&fit=crop&w=256&q=80",
                "role": "ADMIN",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    users = sa.sql.table("users", sa.column("id", sa.String(length=36)))
    op.execute(users.delete().where(users.c.id.in_(USER_IDS)))
