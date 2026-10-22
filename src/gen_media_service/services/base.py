from gen_media_service.repository.base import BaseRepository


class BaseService:
    def __init__(self, repository: BaseRepository | None = None) -> None:
        self._repository = repository
