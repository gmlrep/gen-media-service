from gen_media_service.schema.base import BaseSchema


class ProviderWebhook(BaseSchema):
    external_id: str
    status: str  # completed | failed
    result_url: str | None = None
    error_type: str | None = None  # technical | moderation | payload
