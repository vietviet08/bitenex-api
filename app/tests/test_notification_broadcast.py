import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.notification.models import Notification

INTERNAL_TOKEN = "TEST_INTERNAL_TOKEN"


def _internal_auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {INTERNAL_TOKEN}"}


@pytest.mark.asyncio
async def test_internal_broadcast_accepts_enum_value_strings(client: AsyncClient, db_session):
    response = await client.post(
        "/api/v1/notifications/broadcast",
        headers=_internal_auth_header(),
        json={
            "user_ids": ["user-notify-001"],
            "type": "PROMOTION",
            "title": "Abandoned cart reminder",
            "body": "Return to checkout",
            "data": {
                "journey": "abandoned_cart_recovery",
                "cart_id": "cart-001",
                "reminder_stage": 1,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Notification queued for 1 users"

    result = await db_session.execute(select(Notification))
    notifications = result.scalars().all()
    assert len(notifications) == 1
    assert notifications[0].type == "PROMOTION"
    assert notifications[0].channel == "PUSH"
    assert notifications[0].title == "Abandoned cart reminder"
