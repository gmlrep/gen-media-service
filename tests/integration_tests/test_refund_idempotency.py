import asyncio
import json
import uuid

import pytest
from httpx import AsyncClient

from gen_media_service.adapters.provider import ProviderError
from tests.conftest import FakeProviderClient


@pytest.mark.asyncio
async def test_ten_concurrent_failed_webhooks_on_last_leg_refund_once(
    client: AsyncClient,
    sign,
    funded_user: int,
    fake_provider: FakeProviderClient,
    app,
) -> None:
    # Force first leg (alpha) to fail sync so we land on beta as last waiting attempt.
    fake_provider.outcomes["alpha"] = [ProviderError("alpha down")]
    external_id = f"beta-last-{uuid.uuid4()}"
    fake_provider.outcomes["beta"] = [external_id]

    gen = await client.post(
        "/generate",
        json={
            "user_id": funded_user,
            "model_slug": "image-fast",
            "prompt": "refund race",
            "ref_images": [],
        },
    )
    assert gen.status_code == 200, gen.text
    task_id = gen.json()["task_id"]

    task = await client.get(f"/tasks/{task_id}")
    assert task.json()["status"] == "running"
    assert any(a["provider"] == "beta" and a["status"] == "waiting" for a in task.json()["attempts"])

    before = await client.get(f"/users/{funded_user}/balance")
    balance_before = before.json()["balance"]

    payload = {
        "external_id": external_id,
        "status": "failed",
        "error_type": "technical",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = sign(body)

    results = await asyncio.gather(
        *[
            client.post("/webhooks/providers/beta", content=body, headers=headers)
            for _ in range(10)
        ]
    )
    assert all(r.status_code == 200 for r in results)

    task = await client.get(f"/tasks/{task_id}")
    assert task.json()["status"] == "failed"

    after = await client.get(f"/users/{funded_user}/balance")
    data = after.json()
    assert data["balance"] == balance_before + 2  # image-fast price refunded once
    refunds = [e for e in data["recent_ledger"] if e["kind"] == "refund"]
    assert len(refunds) == 1
    assert refunds[0]["external_ref"] == str(task_id)
