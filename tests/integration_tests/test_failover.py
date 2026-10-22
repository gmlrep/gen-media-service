import json
import uuid

import pytest
from httpx import AsyncClient

from gen_media_service.adapters.provider import ProviderError
from tests.conftest import FakeProviderClient


@pytest.mark.asyncio
async def test_first_leg_failure_completes_on_second_with_two_attempts(
    client: AsyncClient,
    sign,
    funded_user: int,
    fake_provider: FakeProviderClient,
) -> None:
    fake_provider.outcomes["alpha"] = [ProviderError("sync fail")]
    beta_external = f"beta-ok-{uuid.uuid4()}"
    fake_provider.outcomes["beta"] = [beta_external]

    gen = await client.post(
        "/generate",
        json={
            "user_id": funded_user,
            "model_slug": "image-fast",
            "prompt": "failover",
            "ref_images": ["r1"],
        },
    )
    assert gen.status_code == 200, gen.text
    task_id = gen.json()["task_id"]

    mid = await client.get(f"/tasks/{task_id}")
    mid_data = mid.json()
    assert len(mid_data["attempts"]) == 2
    assert mid_data["attempts"][0]["provider"] == "alpha"
    assert mid_data["attempts"][0]["status"] == "failed"
    assert mid_data["attempts"][0]["error_type"] == "technical"
    assert mid_data["attempts"][1]["provider"] == "beta"
    assert mid_data["attempts"][1]["status"] == "waiting"

    body = json.dumps(
        {
            "external_id": beta_external,
            "status": "completed",
            "result_url": "https://cdn.example/ok.bin",
        },
        separators=(",", ":"),
    ).encode()
    resp = await client.post("/webhooks/providers/beta", content=body, headers=sign(body))
    assert resp.status_code == 200

    final = await client.get(f"/tasks/{task_id}")
    data = final.json()
    assert data["status"] == "completed"
    assert data["result_url"] == "https://cdn.example/ok.bin"
    assert len(data["attempts"]) == 2
