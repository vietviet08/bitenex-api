import pytest

from app.core.exceptions import AuthorizationError, NotFoundError
from app.modules.merchant.models import MenuItem, Merchant
from app.modules.merchant.schemas import MenuItemCreate, MenuItemUpdate, MerchantCreate, MerchantUpdate
from app.modules.merchant.service import MerchantService
from app.modules.user.models import User
from app.shared.enums import MerchantStatus


@pytest.mark.asyncio
async def test_list_and_search_active_merchants_only(db_session):
    service = MerchantService(db_session)

    alpha = Merchant(
        user_id="u-alpha",
        name="Alpha Foods",
        slug="alpha-foods",
        address="1 Alpha St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    beta = Merchant(
        user_id="u-beta",
        name="Beta Kitchen",
        slug="beta-kitchen",
        address="2 Beta St",
        city="Hanoi",
        status=MerchantStatus.ACTIVE.value,
    )
    pending = Merchant(
        user_id="u-pending",
        name="Pending Cafe",
        slug="pending-cafe",
        address="3 Pending St",
        city="Hanoi",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add_all([alpha, beta, pending])
    await db_session.flush()

    db_session.add_all(
        [
            MenuItem(
                merchant_id=alpha.id,
                name="Pho",
                price=4.5,
                category="Viet",
            ),
            MenuItem(
                merchant_id=beta.id,
                name="Burger",
                price=8.5,
                category="Western",
            ),
        ]
    )
    await db_session.flush()

    items, total = await service.list_merchants(city="hanoi", category="viet", page=1, per_page=20)
    assert total == 1
    assert len(items) == 1
    assert items[0].id == alpha.id

    search_results = await service.search_merchants("food")
    assert len(search_results) == 1
    assert search_results[0].id == alpha.id


@pytest.mark.asyncio
async def test_merchant_retrieval_and_approval(db_session):
    service = MerchantService(db_session)

    pending = Merchant(
        user_id="u-merchant",
        name="Pending Bistro",
        slug="pending-bistro",
        address="4 Pending St",
        city="Da Nang",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add(pending)
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await service.get_merchant_by_id(pending.id)

    approved = await service.approve_merchant(pending.id, approved_by="admin-1")
    assert approved.status == MerchantStatus.ACTIVE.value
    approved_again = await service.approve_merchant(pending.id, approved_by="admin-1")
    assert approved_again.status == MerchantStatus.ACTIVE.value

    by_id = await service.get_merchant_by_id(pending.id)
    by_slug = await service.get_merchant_by_slug(pending.slug)
    by_user = await service.get_merchant_by_user_id(pending.user_id)
    assert by_id.id == pending.id
    assert by_slug.id == pending.id
    assert by_user.id == pending.id


@pytest.mark.asyncio
async def test_create_and_update_merchant(db_session):
    service = MerchantService(db_session)

    created = await service.create_merchant(
        MerchantCreate(
            user_id="merchant-user-1",
            name="Merchant Name",
            description="desc",
            address="123 Main St",
            city="HCM",
            min_order_amount=0,
            delivery_fee=2.5,
            estimated_prep_time=30,
        )
    )
    assert created.status == MerchantStatus.PENDING.value
    assert created.slug == "merchant-name"

    created_2 = await service.create_merchant(
        MerchantCreate(
            user_id="merchant-user-2",
            name="Merchant Name",
            description="desc",
            address="456 Main St",
            city="HCM",
            min_order_amount=0,
            delivery_fee=2.5,
            estimated_prep_time=30,
        )
    )
    assert created_2.slug.startswith("merchant-name-")

    updated = await service.update_merchant(
        created.id,
        MerchantUpdate(
            name="Merchant Updated",
                description="Updated description",
                city="Ha Noi",
                phone="+84901234567",
                latitude=21.0285,
                longitude=105.8542,
            logo_url="https://cdn.test/logo.png",
            cover_image_url="https://cdn.test/cover.png",
            delivery_fee=3.0,
        ),
    )
    assert updated.name == "Merchant Updated"
    assert updated.delivery_fee == pytest.approx(3.0)
    assert updated.is_profile_complete is True


@pytest.mark.asyncio
async def test_menu_crud_with_ownership_rules(db_session):
    service = MerchantService(db_session)

    owner = Merchant(
        user_id="merchant-owner-1",
        name="Owner Merchant",
        slug="owner-merchant",
        address="10 Owner St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    other = Merchant(
        user_id="merchant-owner-2",
        name="Other Merchant",
        slug="other-merchant",
        address="11 Other St",
        city="Hue",
        status=MerchantStatus.ACTIVE.value,
    )
    db_session.add_all([owner, other])
    await db_session.flush()

    item = await service.add_menu_item(
        owner.id,
        MenuItemCreate(
            name="Noodle",
            description="Hot noodle",
            price=10.0,
            category="Main",
            is_available=True,
        ),
    )
    assert item.merchant_id == owner.id

    updated = await service.update_menu_item(
        item.id,
        MenuItemUpdate(price=12.0),
        actor_merchant_id=owner.id,
    )
    assert updated.price == pytest.approx(12.0)

    with pytest.raises(AuthorizationError):
        await service.update_menu_item(
            item.id,
            MenuItemUpdate(name="Forbidden"),
            actor_merchant_id=other.id,
        )

    await service.delete_menu_item(item.id, actor_merchant_id=owner.id)
    await service.delete_menu_item(item.id, actor_merchant_id=owner.id)

    menu = await service.get_menu(owner.id)
    assert menu == []

    with pytest.raises(AuthorizationError):
        await service.delete_menu_item(item.id, actor_merchant_id=other.id)


@pytest.mark.asyncio
async def test_list_admin_merchants_with_owner_metadata(db_session):
    service = MerchantService(db_session)

    owner = User(
        email="merchant-owner@example.com",
        password_hash="hashed",
        full_name="Owner Name",
        role="MERCHANT",
        is_active=True,
        is_verified=True,
    )
    db_session.add(owner)
    await db_session.flush()

    merchant = Merchant(
        user_id=owner.id,
        name="Pending for Admin",
        slug="pending-for-admin",
        address="100 Admin St",
        city="HCM",
        status=MerchantStatus.PENDING.value,
    )
    db_session.add(merchant)
    await db_session.flush()

    items, total = await service.list_admin_merchants(
        status=MerchantStatus.PENDING,
        page=1,
        per_page=20,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].id == merchant.id
    assert items[0].owner_email == owner.email
    assert items[0].owner_full_name == owner.full_name
