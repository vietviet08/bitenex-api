"""seed_mock_merchant_catalog_data

Seed mock merchant catalog data for local development and QA:
- merchant owner users
- active merchants
- merchant categories
- menu items
- menu item option groups and options

Revision ID: c9e0f1a2b3c4
Revises: b7c8d9e0f1a2
Create Date: 2026-03-14 00:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e0f1a2b3c4"
down_revision: Union[str, None] = "b7c8d9e0f1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PASSWORD_HASH = "$2b$12$4Tm8dlw.PKKsJmcDAeN8xOPQPOI/zpa5H4De2BoAicyCRtEWsB8f6"  # password123

USER_IDS = (
    "10000000-0000-0000-0000-000000000001",
    "10000000-0000-0000-0000-000000000002",
    "10000000-0000-0000-0000-000000000003",
)

MERCHANT_IDS = (
    "20000000-0000-0000-0000-000000000001",
    "20000000-0000-0000-0000-000000000002",
    "20000000-0000-0000-0000-000000000003",
)

CATEGORY_IDS = (
    "30000000-0000-0000-0000-000000000001",
    "30000000-0000-0000-0000-000000000002",
    "30000000-0000-0000-0000-000000000003",
    "30000000-0000-0000-0000-000000000004",
    "30000000-0000-0000-0000-000000000005",
    "30000000-0000-0000-0000-000000000006",
)

MENU_ITEM_IDS = (
    "40000000-0000-0000-0000-000000000001",
    "40000000-0000-0000-0000-000000000002",
    "40000000-0000-0000-0000-000000000003",
    "40000000-0000-0000-0000-000000000004",
    "40000000-0000-0000-0000-000000000005",
    "40000000-0000-0000-0000-000000000006",
    "40000000-0000-0000-0000-000000000007",
    "40000000-0000-0000-0000-000000000008",
    "40000000-0000-0000-0000-000000000009",
)

OPTION_GROUP_IDS = (
    "50000000-0000-0000-0000-000000000001",
    "50000000-0000-0000-0000-000000000002",
    "50000000-0000-0000-0000-000000000003",
    "50000000-0000-0000-0000-000000000004",
    "50000000-0000-0000-0000-000000000005",
    "50000000-0000-0000-0000-000000000006",
)

OPTION_IDS = (
    "60000000-0000-0000-0000-000000000001",
    "60000000-0000-0000-0000-000000000002",
    "60000000-0000-0000-0000-000000000003",
    "60000000-0000-0000-0000-000000000004",
    "60000000-0000-0000-0000-000000000005",
    "60000000-0000-0000-0000-000000000006",
    "60000000-0000-0000-0000-000000000007",
    "60000000-0000-0000-0000-000000000008",
    "60000000-0000-0000-0000-000000000009",
    "60000000-0000-0000-0000-000000000010",
    "60000000-0000-0000-0000-000000000011",
    "60000000-0000-0000-0000-000000000012",
    "60000000-0000-0000-0000-000000000013",
    "60000000-0000-0000-0000-000000000014",
    "60000000-0000-0000-0000-000000000015",
    "60000000-0000-0000-0000-000000000016",
    "60000000-0000-0000-0000-000000000017",
    "60000000-0000-0000-0000-000000000018",
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

merchants_table = sa.table(
    "merchants",
    sa.column("id", sa.String(length=36)),
    sa.column("user_id", sa.String(length=36)),
    sa.column("name", sa.String(length=100)),
    sa.column("slug", sa.String(length=100)),
    sa.column("description", sa.Text()),
    sa.column("logo_url", sa.Text()),
    sa.column("cover_image_url", sa.Text()),
    sa.column("status", sa.String(length=20)),
    sa.column("is_featured", sa.Boolean()),
    sa.column("address", sa.String(length=255)),
    sa.column("city", sa.String(length=100)),
    sa.column("latitude", sa.Float()),
    sa.column("longitude", sa.Float()),
    sa.column("phone", sa.String(length=20)),
    sa.column("min_order_amount", sa.Float()),
    sa.column("delivery_fee", sa.Float()),
    sa.column("estimated_prep_time", sa.Integer()),
    sa.column("average_rating", sa.Float()),
    sa.column("total_orders", sa.Integer()),
    sa.column("is_deleted", sa.Boolean()),
)

merchant_categories_table = sa.table(
    "merchant_categories",
    sa.column("id", sa.String(length=36)),
    sa.column("name", sa.String(length=50)),
    sa.column("slug", sa.String(length=50)),
    sa.column("icon_url", sa.Text()),
    sa.column("is_deleted", sa.Boolean()),
)

menu_items_table = sa.table(
    "menu_items",
    sa.column("id", sa.String(length=36)),
    sa.column("merchant_id", sa.String(length=36)),
    sa.column("name", sa.String(length=100)),
    sa.column("description", sa.Text()),
    sa.column("price", sa.Float()),
    sa.column("image_url", sa.Text()),
    sa.column("category", sa.String(length=50)),
    sa.column("is_available", sa.Boolean()),
    sa.column("is_featured", sa.Boolean()),
    sa.column("is_deleted", sa.Boolean()),
)

option_groups_table = sa.table(
    "menu_item_option_groups",
    sa.column("id", sa.String(length=36)),
    sa.column("menu_item_id", sa.String(length=36)),
    sa.column("name", sa.String(length=100)),
    sa.column("selection_type", sa.String(length=20)),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_required", sa.Boolean()),
    sa.column("is_deleted", sa.Boolean()),
)

options_table = sa.table(
    "menu_item_options",
    sa.column("id", sa.String(length=36)),
    sa.column("option_group_id", sa.String(length=36)),
    sa.column("name", sa.String(length=100)),
    sa.column("price_delta", sa.Float()),
    sa.column("sort_order", sa.Integer()),
    sa.column("is_available", sa.Boolean()),
    sa.column("is_deleted", sa.Boolean()),
)


def upgrade() -> None:
    op.bulk_insert(
        users_table,
        [
            {
                "id": USER_IDS[0],
                "email": "merchant.pho@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "Nguyen Minh Quan",
                "phone": "0901000001",
                "avatar_url": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=256&q=80",
                "role": "MERCHANT",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
            {
                "id": USER_IDS[1],
                "email": "merchant.banhmi@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "Tran Ha Linh",
                "phone": "0901000002",
                "avatar_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=256&q=80",
                "role": "MERCHANT",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
            {
                "id": USER_IDS[2],
                "email": "merchant.comtam@bitenex.local",
                "password_hash": PASSWORD_HASH,
                "full_name": "Le Duc Thang",
                "phone": "0901000003",
                "avatar_url": "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=256&q=80",
                "role": "MERCHANT",
                "is_active": True,
                "is_verified": True,
                "is_deleted": False,
            },
        ],
    )

    op.bulk_insert(
        merchant_categories_table,
        [
            {
                "id": CATEGORY_IDS[0],
                "name": "Vietnamese",
                "slug": "vietnamese",
                "icon_url": "https://img.icons8.com/color/96/noodles.png",
                "is_deleted": False,
            },
            {
                "id": CATEGORY_IDS[1],
                "name": "Noodles",
                "slug": "noodles",
                "icon_url": "https://img.icons8.com/color/96/ramen.png",
                "is_deleted": False,
            },
            {
                "id": CATEGORY_IDS[2],
                "name": "Sandwiches",
                "slug": "sandwiches",
                "icon_url": "https://img.icons8.com/color/96/sandwich.png",
                "is_deleted": False,
            },
            {
                "id": CATEGORY_IDS[3],
                "name": "Rice",
                "slug": "rice",
                "icon_url": "https://img.icons8.com/color/96/rice-bowl.png",
                "is_deleted": False,
            },
            {
                "id": CATEGORY_IDS[4],
                "name": "Beverages",
                "slug": "beverages",
                "icon_url": "https://img.icons8.com/color/96/bubble-tea-1.png",
                "is_deleted": False,
            },
            {
                "id": CATEGORY_IDS[5],
                "name": "Dessert",
                "slug": "dessert",
                "icon_url": "https://img.icons8.com/color/96/ice-cream.png",
                "is_deleted": False,
            },
        ],
    )

    op.bulk_insert(
        merchants_table,
        [
            {
                "id": MERCHANT_IDS[0],
                "user_id": USER_IDS[0],
                "name": "Saigon Pho House",
                "slug": "saigon-pho-house",
                "description": "Pho, bun bo and fresh Vietnamese sides prepared for quick lunch and dinner orders.",
                "logo_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=200&q=80",
                "cover_image_url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=1200&q=80",
                "status": "ACTIVE",
                "is_featured": True,
                "address": "12 Nguyen Hue, Ben Nghe Ward, District 1",
                "city": "Ho Chi Minh City",
                "latitude": 10.776889,
                "longitude": 106.700806,
                "phone": "02838228881",
                "min_order_amount": 50000.0,
                "delivery_fee": 18000.0,
                "estimated_prep_time": 20,
                "average_rating": 4.8,
                "total_orders": 1280,
                "is_deleted": False,
            },
            {
                "id": MERCHANT_IDS[1],
                "user_id": USER_IDS[1],
                "name": "Banh Mi 88",
                "slug": "banh-mi-88",
                "description": "Classic banh mi with grilled meats, pate and crunchy pickles plus quick snacks and drinks.",
                "logo_url": "https://images.unsplash.com/photo-1528605248644-14dd04022da1?auto=format&fit=crop&w=200&q=80",
                "cover_image_url": "https://images.unsplash.com/photo-1466978913421-dad2ebd01d17?auto=format&fit=crop&w=1200&q=80",
                "status": "ACTIVE",
                "is_featured": True,
                "address": "88 Vo Van Tan, Ward 6, District 3",
                "city": "Ho Chi Minh City",
                "latitude": 10.777119,
                "longitude": 106.689917,
                "phone": "02839308888",
                "min_order_amount": 30000.0,
                "delivery_fee": 15000.0,
                "estimated_prep_time": 15,
                "average_rating": 4.6,
                "total_orders": 940,
                "is_deleted": False,
            },
            {
                "id": MERCHANT_IDS[2],
                "user_id": USER_IDS[2],
                "name": "Com Tam District 1",
                "slug": "com-tam-district-1",
                "description": "Broken rice combos with grilled pork, egg cake and late-night comfort food favorites.",
                "logo_url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?auto=format&fit=crop&w=200&q=80",
                "cover_image_url": "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1200&q=80",
                "status": "ACTIVE",
                "is_featured": False,
                "address": "45 Co Giang, Co Giang Ward, District 1",
                "city": "Ho Chi Minh City",
                "latitude": 10.764526,
                "longitude": 106.692146,
                "phone": "02838229999",
                "min_order_amount": 45000.0,
                "delivery_fee": 17000.0,
                "estimated_prep_time": 18,
                "average_rating": 4.7,
                "total_orders": 1115,
                "is_deleted": False,
            },
        ],
    )

    op.bulk_insert(
        menu_items_table,
        [
            {
                "id": MENU_ITEM_IDS[0],
                "merchant_id": MERCHANT_IDS[0],
                "name": "Pho Bo Tai",
                "description": "Traditional rare beef pho with rich broth, herbs and rice noodles.",
                "price": 68000.0,
                "image_url": "https://images.unsplash.com/photo-1582878826629-29b7ad1cdc43?auto=format&fit=crop&w=900&q=80",
                "category": "Noodles",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[1],
                "merchant_id": MERCHANT_IDS[0],
                "name": "Bun Bo Hue",
                "description": "Spicy central-style beef noodle soup with lemongrass aroma.",
                "price": 72000.0,
                "image_url": "https://images.unsplash.com/photo-1617622141675-d3005b9067c5?auto=format&fit=crop&w=900&q=80",
                "category": "Noodles",
                "is_available": True,
                "is_featured": False,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[2],
                "merchant_id": MERCHANT_IDS[0],
                "name": "Goi Cuon Tom Thit",
                "description": "Fresh spring rolls with shrimp, pork, vermicelli and peanut sauce.",
                "price": 42000.0,
                "image_url": "https://images.unsplash.com/photo-1563245372-f21724e3856d?auto=format&fit=crop&w=900&q=80",
                "category": "Vietnamese",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[3],
                "merchant_id": MERCHANT_IDS[1],
                "name": "Banh Mi Thit Nuong",
                "description": "Grilled pork banh mi with pate, cucumber, herbs and pickled vegetables.",
                "price": 39000.0,
                "image_url": "https://images.unsplash.com/photo-1627308595229-7830a5c91f9f?auto=format&fit=crop&w=900&q=80",
                "category": "Sandwiches",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[4],
                "merchant_id": MERCHANT_IDS[1],
                "name": "Banh Mi Ga Xa",
                "description": "Lemongrass chicken banh mi with homemade mayo and crisp herbs.",
                "price": 42000.0,
                "image_url": "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?auto=format&fit=crop&w=900&q=80",
                "category": "Sandwiches",
                "is_available": True,
                "is_featured": False,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[5],
                "merchant_id": MERCHANT_IDS[1],
                "name": "Tra Dao Cam Sa",
                "description": "Peach tea with lemongrass syrup and citrus slices.",
                "price": 28000.0,
                "image_url": "https://images.unsplash.com/photo-1499636136210-6f4ee915583e?auto=format&fit=crop&w=900&q=80",
                "category": "Beverages",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[6],
                "merchant_id": MERCHANT_IDS[2],
                "name": "Com Tam Suon Bi Cha",
                "description": "Broken rice with grilled pork chop, shredded pork skin and steamed egg cake.",
                "price": 69000.0,
                "image_url": "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=900&q=80",
                "category": "Rice",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[7],
                "merchant_id": MERCHANT_IDS[2],
                "name": "Com Tam Suon Trung",
                "description": "Broken rice with grilled pork chop and sunny-side-up egg.",
                "price": 62000.0,
                "image_url": "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=900&q=80",
                "category": "Rice",
                "is_available": True,
                "is_featured": False,
                "is_deleted": False,
            },
            {
                "id": MENU_ITEM_IDS[8],
                "merchant_id": MERCHANT_IDS[2],
                "name": "Sua Chua Nep Cam",
                "description": "Sticky black rice yogurt dessert served chilled.",
                "price": 26000.0,
                "image_url": "https://images.unsplash.com/photo-1488477181946-6428a0291777?auto=format&fit=crop&w=900&q=80",
                "category": "Dessert",
                "is_available": True,
                "is_featured": True,
                "is_deleted": False,
            },
        ],
    )

    op.bulk_insert(
        option_groups_table,
        [
            {
                "id": OPTION_GROUP_IDS[0],
                "menu_item_id": MENU_ITEM_IDS[0],
                "name": "Size",
                "selection_type": "single",
                "sort_order": 0,
                "is_required": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_GROUP_IDS[1],
                "menu_item_id": MENU_ITEM_IDS[0],
                "name": "Add-ons",
                "selection_type": "multiple",
                "sort_order": 1,
                "is_required": False,
                "is_deleted": False,
            },
            {
                "id": OPTION_GROUP_IDS[2],
                "menu_item_id": MENU_ITEM_IDS[3],
                "name": "Bread Type",
                "selection_type": "single",
                "sort_order": 0,
                "is_required": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_GROUP_IDS[3],
                "menu_item_id": MENU_ITEM_IDS[3],
                "name": "Extra Fillings",
                "selection_type": "multiple",
                "sort_order": 1,
                "is_required": False,
                "is_deleted": False,
            },
            {
                "id": OPTION_GROUP_IDS[4],
                "menu_item_id": MENU_ITEM_IDS[6],
                "name": "Egg Preference",
                "selection_type": "single",
                "sort_order": 0,
                "is_required": False,
                "is_deleted": False,
            },
            {
                "id": OPTION_GROUP_IDS[5],
                "menu_item_id": MENU_ITEM_IDS[6],
                "name": "Sides",
                "selection_type": "multiple",
                "sort_order": 1,
                "is_required": False,
                "is_deleted": False,
            },
        ],
    )

    op.bulk_insert(
        options_table,
        [
            {
                "id": OPTION_IDS[0],
                "option_group_id": OPTION_GROUP_IDS[0],
                "name": "Small",
                "price_delta": 0.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[1],
                "option_group_id": OPTION_GROUP_IDS[0],
                "name": "Medium",
                "price_delta": 10000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[2],
                "option_group_id": OPTION_GROUP_IDS[0],
                "name": "Large",
                "price_delta": 18000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[3],
                "option_group_id": OPTION_GROUP_IDS[1],
                "name": "Extra Beef",
                "price_delta": 22000.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[4],
                "option_group_id": OPTION_GROUP_IDS[1],
                "name": "Soft-Boiled Egg",
                "price_delta": 12000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[5],
                "option_group_id": OPTION_GROUP_IDS[1],
                "name": "Extra Noodles",
                "price_delta": 10000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[6],
                "option_group_id": OPTION_GROUP_IDS[2],
                "name": "Traditional Baguette",
                "price_delta": 0.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[7],
                "option_group_id": OPTION_GROUP_IDS[2],
                "name": "Whole Wheat Roll",
                "price_delta": 4000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[8],
                "option_group_id": OPTION_GROUP_IDS[2],
                "name": "Butter Toasted",
                "price_delta": 5000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[9],
                "option_group_id": OPTION_GROUP_IDS[3],
                "name": "Extra Pork",
                "price_delta": 15000.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[10],
                "option_group_id": OPTION_GROUP_IDS[3],
                "name": "Cheese",
                "price_delta": 8000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[11],
                "option_group_id": OPTION_GROUP_IDS[3],
                "name": "Fried Egg",
                "price_delta": 9000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[12],
                "option_group_id": OPTION_GROUP_IDS[4],
                "name": "No Egg",
                "price_delta": 0.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[13],
                "option_group_id": OPTION_GROUP_IDS[4],
                "name": "Sunny Side Up",
                "price_delta": 8000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[14],
                "option_group_id": OPTION_GROUP_IDS[4],
                "name": "Omelette",
                "price_delta": 10000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[15],
                "option_group_id": OPTION_GROUP_IDS[5],
                "name": "Pickled Vegetables",
                "price_delta": 5000.0,
                "sort_order": 0,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[16],
                "option_group_id": OPTION_GROUP_IDS[5],
                "name": "Extra Scallion Oil",
                "price_delta": 4000.0,
                "sort_order": 1,
                "is_available": True,
                "is_deleted": False,
            },
            {
                "id": OPTION_IDS[17],
                "option_group_id": OPTION_GROUP_IDS[5],
                "name": "Shredded Pork Skin",
                "price_delta": 12000.0,
                "sort_order": 2,
                "is_available": True,
                "is_deleted": False,
            },
        ],
    )


def downgrade() -> None:
    options = sa.sql.table("menu_item_options", sa.column("id", sa.String(length=36)))
    option_groups = sa.sql.table(
        "menu_item_option_groups", sa.column("id", sa.String(length=36))
    )
    menu_items = sa.sql.table("menu_items", sa.column("id", sa.String(length=36)))
    merchants = sa.sql.table("merchants", sa.column("id", sa.String(length=36)))
    merchant_categories = sa.sql.table(
        "merchant_categories", sa.column("id", sa.String(length=36))
    )
    users = sa.sql.table("users", sa.column("id", sa.String(length=36)))

    op.execute(options.delete().where(options.c.id.in_(OPTION_IDS)))
    op.execute(option_groups.delete().where(option_groups.c.id.in_(OPTION_GROUP_IDS)))
    op.execute(menu_items.delete().where(menu_items.c.id.in_(MENU_ITEM_IDS)))
    op.execute(merchants.delete().where(merchants.c.id.in_(MERCHANT_IDS)))
    op.execute(merchant_categories.delete().where(merchant_categories.c.id.in_(CATEGORY_IDS)))
    op.execute(users.delete().where(users.c.id.in_(USER_IDS)))
