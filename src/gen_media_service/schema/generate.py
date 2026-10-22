from datetime import datetime

from gen_media_service.schema.base import BaseSchema


class GenerateRequest(BaseSchema):
    user_id: int
    model_slug: str
    prompt: str
    ref_images: list[str] = []


class GenerateResponse(BaseSchema):
    task_id: int


class AttemptHistoryItem(BaseSchema):
    provider: str
    status: str
    error_type: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class TaskRead(BaseSchema):
    id: int
    status: str
    model_slug: str
    current_provider: str | None = None
    result_url: str | None = None
    attempts: list[AttemptHistoryItem]
