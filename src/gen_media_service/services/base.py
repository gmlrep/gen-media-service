from typing import Any

from gen_media_service.repository.base import BaseRepository


class BaseService:
    def __init__(self, repository: BaseRepository[Any] | None = None) -> None:
        self._repository = repository
