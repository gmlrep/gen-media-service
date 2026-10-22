from gen_media_service.core.exceptions import ValidationError
from gen_media_service.repository.ledger import LedgerRepository
from gen_media_service.repository.user import UserRepository
from gen_media_service.schema.payment import PaymentWebhook
from gen_media_service.schema.user import BalanceRead, LedgerEntryRead
from gen_media_service.services.base import BaseService


class PaymentService(BaseService):
    def __init__(
        self,
        ledger_repository: LedgerRepository,
        user_repository: UserRepository,
    ) -> None:
        self.ledger_repository = ledger_repository
        self.user_repository = user_repository
        super().__init__(ledger_repository)

    async def apply_payment(self, payload: PaymentWebhook) -> bool:
        if payload.status != "succeeded":
            raise ValidationError(f"Unsupported payment status: {payload.status}")
        if payload.tokens <= 0:
            raise ValidationError("tokens must be positive")

        async with self.ledger_repository.session_factory() as session:
            await self.user_repository.get_or_create(session, payload.user_id)
            applied = await self.ledger_repository.try_apply(
                session,
                user_id=payload.user_id,
                amount=payload.tokens,
                kind="payment",
                external_ref=payload.payment_id,
            )
            return applied

    async def get_balance(self, user_id: int) -> BalanceRead:
        async with self.ledger_repository.session_factory() as session:
            user = await self.user_repository.get_or_create(session, user_id)
            entries = await self.ledger_repository.recent_for_user(session, user_id)
            return BalanceRead(
                user_id=user.id,
                balance=user.balance,
                recent_ledger=[LedgerEntryRead.model_validate(e) for e in entries],
            )
