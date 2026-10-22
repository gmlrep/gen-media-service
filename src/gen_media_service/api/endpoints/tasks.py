from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from gen_media_service.core.container import Container
from gen_media_service.schema.generate import TaskRead
from gen_media_service.services.generation import GenerationService

router = APIRouter(tags=["tasks"])


@router.get("/tasks/{task_id}", response_model=TaskRead)
@inject
async def get_task(
    task_id: int,
    service: GenerationService = Depends(Provide[Container.generation_service]),
) -> TaskRead:
    return await service.get_task(task_id)
