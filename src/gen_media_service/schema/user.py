from datetime import datetime

from gen_media_service.schema.base import BaseSchema


class LedgerEntryRead(BaseSchema):
    id: int
    amount: int
    kind: str
    external_ref: str
    created_at: datetime


class BalanceRead(BaseSchema):
    user_id: int
    balance: int
    recent_ledger: list[LedgerEntryRead]
