from fastapi import APIRouter

from gen_media_service.api.endpoints import generate, tasks, users, webhooks
from gen_media_service.api.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(generate.router)
api_router.include_router(tasks.router)
api_router.include_router(users.router)
api_router.include_router(webhooks.router)
