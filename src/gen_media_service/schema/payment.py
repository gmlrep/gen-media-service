from gen_media_service.schema.base import BaseSchema


class PaymentWebhook(BaseSchema):
    payment_id: str
    user_id: int
    tokens: int
    status: str
