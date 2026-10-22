from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DB_HOST", os.getenv("DB_HOST", "localhost"))
os.environ.setdefault("DB_PORT", os.getenv("DB_PORT", "5432"))
os.environ.setdefault("DB_USER", os.getenv("DB_USER", "postgres"))
os.environ.setdefault("DB_PASSWORD", os.getenv("DB_PASSWORD", "postgres"))
os.environ.setdefault("DB_NAME", os.getenv("DB_NAME", "gen_media"))
os.environ.setdefault("WEBHOOK_SECRET", "dev-webhook-secret")
os.environ.setdefault("PROVIDER_TIMEOUT", "60")
os.environ.setdefault("WATCHDOG_INTERVAL_SECONDS", "0.2")

from gen_media_service.__main__ import create_app
from gen_media_service.adapters.provider import ProviderSubmitResult
from gen_media_service.core.config import get_settings
from gen_media_service.core.security import sign_body


@dataclass
class FakeProviderClient:
    """Deterministic provider stub for integration tests."""

    outcomes: dict[str, list[str | Exception]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    async def submit_task(
        self,
        *,
        provider: str,
        prompt: str,
        ref_images: list[str],
        model_slug: str,
    ) -> ProviderSubmitResult:
        _ = prompt, ref_images, model_slug
        self.calls.append(provider)
        queue = self.outcomes.setdefault(provider, [])
        if queue:
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return ProviderSubmitResult(external_id=str(item))
        external_id = f"fake-{provider}-{len(self.calls)}-{uuid.uuid4().hex[:8]}"
        return ProviderSubmitResult(external_id=external_id)


@pytest.fixture
def webhook_secret() -> str:
    return get_settings().providers.WEBHOOK_SECRET


@pytest.fixture
def sign(webhook_secret: str) -> Callable[[bytes], dict[str, str]]:
    def _sign(body: bytes) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Signature": sign_body(body, webhook_secret),
        }

    return _sign


@pytest_asyncio.fixture
async def fake_provider() -> FakeProviderClient:
    return FakeProviderClient()


@pytest_asyncio.fixture
async def app(fake_provider: FakeProviderClient):
    get_settings.cache_clear()
    application = create_app()
    container = application.state.container
    container.provider_client.override(fake_provider)
    yield application
    container.provider_client.reset_override()
    await container.db().dispose()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def funded_user(
    client: AsyncClient, sign: Callable[[bytes], dict[str, str]]
) -> int:
    user_id = 10_000 + (uuid.uuid4().int % 90_000)
    payment_id = f"seed-{uuid.uuid4()}"
    body = (
        f'{{"payment_id":"{payment_id}","user_id":{user_id},'
        f'"tokens":1000,"status":"succeeded"}}'
    ).encode()
    resp = await client.post("/webhooks/payments", content=body, headers=sign(body))
    assert resp.status_code == 200, resp.text
    return user_id
