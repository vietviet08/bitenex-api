from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.modules.call.schemas import CallActionResponse, CallTokenResponse
from app.modules.call.service import CallService

router = APIRouter(prefix="/calls", tags=["Calls"])


def get_call_service(db: AsyncSession = Depends(get_db)) -> CallService:
    return CallService(db)


@router.post(
    "/orders/{order_id}/start",
    response_model=CallTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start order voice call",
)
async def start_order_call(
    order_id: str,
    user: CurrentUser,
    service: CallService = Depends(get_call_service),
) -> CallTokenResponse:
    return await service.start_call(order_id, actor_user_id=user.user_id, actor_role=user.role)


@router.post("/{call_id}/accept", response_model=CallTokenResponse, summary="Accept voice call")
async def accept_call(
    call_id: str,
    user: CurrentUser,
    service: CallService = Depends(get_call_service),
) -> CallTokenResponse:
    return await service.accept_call(call_id, actor_user_id=user.user_id)


@router.post("/{call_id}/reject", response_model=CallActionResponse, summary="Reject voice call")
async def reject_call(
    call_id: str,
    user: CurrentUser,
    service: CallService = Depends(get_call_service),
) -> CallActionResponse:
    return await service.reject_call(call_id, actor_user_id=user.user_id)


@router.post("/{call_id}/end", response_model=CallActionResponse, summary="End voice call")
async def end_call(
    call_id: str,
    user: CurrentUser,
    service: CallService = Depends(get_call_service),
) -> CallActionResponse:
    return await service.end_call(call_id, actor_user_id=user.user_id)


@router.get("/{call_id}", response_model=CallActionResponse, summary="Get voice call")
async def get_call(
    call_id: str,
    user: CurrentUser,
    service: CallService = Depends(get_call_service),
) -> CallActionResponse:
    return await service.get_call(call_id, actor_user_id=user.user_id)
