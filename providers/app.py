"""Configurable fake provider used as alpha/beta in docker-compose and tests."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import random
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Response
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProviderConfig(BaseSettings):
    PROVIDER_NAME: str = "alpha"
    WEBHOOK_URL: str = "http://api:8000/webhooks/providers/alpha"
    WEBHOOK_SECRET: str = "dev-webhook-secret"
    WEBHOOK_DELAY_MIN: float = 2.0
    WEBHOOK_DELAY_MAX: float = 20.0
    FAILURE_RATE: float = 0.0
    ERROR_TYPE: str = "technical"  # technical | moderation | payload
    SYNC_FAIL_MODE: str = "none"  # none | 503 | timeout
    WEBHOOK_DUPLICATE: bool = False
    WEBHOOK_CONCURRENT_DUPLICATE: bool = False
    WEBHOOK_NEVER: bool = False
    WEBHOOK_AFTER_TIMEOUT: bool = False
    FORCE_RESULT: str = ""  # completed | failed | empty = random by FAILURE_RATE


class TaskRequest(BaseModel):
    prompt: str
    ref_images: list[str] = Field(default_factory=list)
    model_slug: str = ""


config = ProviderConfig()
_background_tasks: set[asyncio.Task] = set()


def _sign(body: bytes) -> str:
    return hmac.new(config.WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _send_webhook(payload: dict) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Signature": _sign(body),
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        await client.post(config.WEBHOOK_URL, content=body, headers=headers)


async def _deliver_outcome(external_id: str) -> None:
    if config.WEBHOOK_NEVER:
        return

    delay_min = config.WEBHOOK_DELAY_MIN
    delay_max = config.WEBHOOK_DELAY_MAX
    if config.WEBHOOK_AFTER_TIMEOUT:
        delay_min = max(delay_min, 65.0)
        delay_max = max(delay_max, 70.0)

    await asyncio.sleep(random.uniform(delay_min, delay_max))

    force = config.FORCE_RESULT.strip().lower()
    if force == "completed":
        failed = False
    elif force == "failed":
        failed = True
    else:
        failed = random.random() < config.FAILURE_RATE

    if failed:
        payload = {
            "external_id": external_id,
            "status": "failed",
            "error_type": config.ERROR_TYPE,
        }
    else:
        payload = {
            "external_id": external_id,
            "status": "completed",
            "result_url": f"https://cdn.example/{config.PROVIDER_NAME}/{external_id}.bin",
        }

    if config.WEBHOOK_CONCURRENT_DUPLICATE:
        await asyncio.gather(_send_webhook(payload), _send_webhook(payload))
    else:
        await _send_webhook(payload)
        if config.WEBHOOK_DUPLICATE:
            await _send_webhook(payload)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    for task in list(_background_tasks):
        task.cancel()


app = FastAPI(title=f"fake-provider-{config.PROVIDER_NAME}", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": config.PROVIDER_NAME}


@app.post("/tasks", status_code=202)
async def create_task(payload: TaskRequest):
    _ = payload
    mode = config.SYNC_FAIL_MODE.lower()
    if mode == "503":
        return Response(status_code=503, content=b"unavailable")
    if mode == "timeout":
        await asyncio.sleep(30)
        return Response(status_code=503, content=b"timeout")

    external_id = f"{config.PROVIDER_NAME}-{uuid.uuid4()}"
    task = asyncio.create_task(_deliver_outcome(external_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"external_id": external_id}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8101"))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
