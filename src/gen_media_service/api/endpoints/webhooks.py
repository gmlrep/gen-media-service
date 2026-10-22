from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request

from gen_media_service.core.config import Settings
from gen_media_service.core.container import Container
from gen_media_service.core.security import verify_signature
from gen_media_service.schema.payment import PaymentWebhook
from gen_media_service.schema.provider_webhook import ProviderWebhook
from gen_media_service.services.generation import GenerationService
from gen_media_service.services.payment import PaymentService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _require_signature(request: Request, settings: Settings) -> bytes:
    body = await request.body()
    signature = request.headers.get("X-Signature")
    if not verify_signature(body, settings.providers.WEBHOOK_SECRET, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    return body


@router.post("/providers/{name}")
@inject
async def provider_webhook(
    name: str,
    request: Request,
    service: GenerationService = Depends(Provide[Container.generation_service]),
    settings: Settings = Depends(Provide[Container.settings]),
) -> dict[str, str]:
    body = await _require_signature(request, settings)
    payload = ProviderWebhook.model_validate_json(body)
    await service.handle_provider_webhook(name, payload)
    return {"status": "ok"}


@router.post("/payments")
@inject
async def payment_webhook(
    request: Request,
    service: PaymentService = Depends(Provide[Container.payment_service]),
    settings: Settings = Depends(Provide[Container.settings]),
) -> dict[str, str]:
    body = await _require_signature(request, settings)
    payload = PaymentWebhook.model_validate_json(body)
    await service.apply_payment(payload)
    return {"status": "ok"}
