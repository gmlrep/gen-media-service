import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from gen_media_service.model.task import TaskAttempt
from tests.conftest import FakeProviderClient


@pytest.mark.asyncio
async def test_late_completed_after_watchdog_is_ignored(
    client: AsyncClient,
    sign,
    funded_user: int,
    fake_provider: FakeProviderClient,
    app,
) -> None:
    """Rule 6: after timeout advance/refund, late completed must not apply result."""
    external_id = f"late-alpha-{uuid.uuid4()}"
    fake_provider.outcomes["alpha"] = [external_id]
    # Second leg also accepted so watchdog can move there after alpha timeout.
    fake_provider.outcomes["beta"] = [f"late-beta-{uuid.uuid4()}"]

    gen = await client.post(
        "/generate",
        json={
            "user_id": funded_user,
            "model_slug": "image-fast",
            "prompt": "late complete",
            "ref_images": [],
        },
    )
    assert gen.status_code == 200, gen.text
    task_id = gen.json()["task_id"]

    # Force the waiting attempt to be already past timeout, then run watchdog claim path.
    db = app.state.container.db()
    async with db.session() as session:
        await session.execute(
            update(TaskAttempt)
            .where(TaskAttempt.external_id == external_id)
            .values(timeout_at=datetime.now(timezone.utc) - timedelta(seconds=5))
        )

    service = app.state.container.generation_service()
    processed = await service.process_timeouts()
    assert processed >= 1

    task = await client.get(f"/tasks/{task_id}")
    data = task.json()
    # Watchdog treated alpha as technical failure and moved to beta (or finished).
    alpha = next(a for a in data["attempts"] if a["provider"] == "alpha")
    assert alpha["status"] == "timeout"
    assert alpha["error_type"] == "technical"

    before = await client.get(f"/users/{funded_user}/balance")
    balance_before = before.json()["balance"]
    status_before = data["status"]
    result_before = data.get("result_url")

    # Late completed for the abandoned alpha attempt
    body = json.dumps(
        {
            "external_id": external_id,
            "status": "completed",
            "result_url": "https://cdn.example/should-ignore.bin",
        },
        separators=(",", ":"),
    ).encode()
    resp = await client.post(
        "/webhooks/providers/alpha", content=body, headers=sign(body)
    )
    assert resp.status_code == 200

    after_task = await client.get(f"/tasks/{task_id}")
    after = after_task.json()
    assert after["result_url"] != "https://cdn.example/should-ignore.bin"
    assert after["result_url"] == result_before
    # Must not flip a failed task back to completed via late webhook
    if status_before == "failed":
        assert after["status"] == "failed"
    else:
        assert after["status"] != "completed" or after["result_url"] != (
            "https://cdn.example/should-ignore.bin"
        )

    after_bal = await client.get(f"/users/{funded_user}/balance")
    # Late completed must not create an extra charge/refund movement
    assert after_bal.json()["balance"] == balance_before
