from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from gen_media_service.core.container import Container
from gen_media_service.schema.user import BalanceRead
from gen_media_service.services.payment import PaymentService

router = APIRouter(tags=["users"])


@router.get("/users/{user_id}/balance", response_model=BalanceRead)
@inject
async def get_balance(
    user_id: int,
    service: PaymentService = Depends(Provide[Container.payment_service]),
) -> BalanceRead:
    return await service.get_balance(user_id)
