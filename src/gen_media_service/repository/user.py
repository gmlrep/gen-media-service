from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gen_media_service.model.user import User
from gen_media_service.repository.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_or_create(self, session: AsyncSession, user_id: int) -> User:
        stmt = (
            insert(User)
            .values(id=user_id, balance=0)
            .on_conflict_do_nothing(index_elements=[User.id])
        )
        await session.execute(stmt)
        await session.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users', 'id'), "
                "GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
            )
        )
        result = await session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        user = result.scalar_one()
        return user

    async def get_for_update(self, session: AsyncSession, user_id: int) -> User | None:
        result = await session.execute(
            select(User).where(User.id == user_id).with_for_update()
        )
        return result.scalar_one_or_none()
