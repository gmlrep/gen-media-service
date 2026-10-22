from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gen_media_service.model.ledger import LedgerEntry
from gen_media_service.model.user import User
from gen_media_service.repository.base import BaseRepository


class LedgerRepository(BaseRepository[LedgerEntry]):
    model = LedgerEntry

    async def try_apply(
        self,
        session: AsyncSession,
        *,
        user_id: int,
        amount: int,
        kind: str,
        external_ref: str,
    ) -> bool:
        """Insert ledger row and adjust balance atomically. Returns False if duplicate."""
        await session.execute(
            insert(User)
            .values(id=user_id, balance=0)
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        await session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
            )
        )

        stmt = (
            insert(LedgerEntry)
            .values(user_id=user_id, amount=amount, kind=kind, external_ref=external_ref)
            .on_conflict_do_nothing(constraint="uq_ledger_kind_ref")
            .returning(LedgerEntry.id)
        )
        result = await session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is None:
            return False

        user_result = await session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = user_result.scalar_one()
        user.balance += amount
        await session.flush()
        return True

    async def sum_for_user(self, session: AsyncSession, user_id: int) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(LedgerEntry.amount), 0)).where(
                LedgerEntry.user_id == user_id
            )
        )
        return int(result.scalar_one())

    async def recent_for_user(
        self, session: AsyncSession, user_id: int, limit: int = 20
    ) -> list[LedgerEntry]:
        result = await session.execute(
            select(LedgerEntry)
            .where(LedgerEntry.user_id == user_id)
            .order_by(LedgerEntry.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
