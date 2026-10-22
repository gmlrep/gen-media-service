from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Generic, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from gen_media_service.model.base_model import BaseModel

ModelType = TypeVar("ModelType", bound=BaseModel)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(
        self,
        session_factory: Callable[..., AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        self.session_factory = session_factory
