from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gen_media_service.model.catalog import GenerationModel, ModelLeg
from gen_media_service.repository.base import BaseRepository


class CatalogRepository(BaseRepository[GenerationModel]):
    model = GenerationModel

    async def get_by_slug(self, session: AsyncSession, slug: str) -> GenerationModel | None:
        result = await session.execute(
            select(GenerationModel)
            .where(GenerationModel.slug == slug)
            .options(selectinload(GenerationModel.legs))
        )
        return result.scalar_one_or_none()

    async def suitable_legs(
        self, session: AsyncSession, slug: str, ref_count: int
    ) -> list[ModelLeg]:
        model = await self.get_by_slug(session, slug)
        if model is None:
            return []
        return [leg for leg in model.legs if leg.max_ref_images >= ref_count]
