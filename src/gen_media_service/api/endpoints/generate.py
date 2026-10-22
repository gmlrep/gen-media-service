from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from gen_media_service.core.container import Container
from gen_media_service.schema.generate import GenerateRequest, GenerateResponse
from gen_media_service.services.generation import GenerationService

router = APIRouter(tags=["generate"])


@router.post("/generate", response_model=GenerateResponse)
@inject
async def create_generation(
    payload: GenerateRequest,
    service: GenerationService = Depends(Provide[Container.generation_service]),
) -> GenerateResponse:
    return await service.generate(payload)
