import asyncio
import json
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_twenty_concurrent_identical_payment_webhooks_credit_once(
    client: AsyncClient,
    sign,
) -> None:
    user_id = 20_000 + (uuid.uuid4().int % 9_000)
    payment_id = f"pay-concurrent-{uuid.uuid4()}"
    payload = {
        "payment_id": payment_id,
        "user_id": user_id,
        "tokens": 50,
        "status": "succeeded",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = sign(body)

    results = await asyncio.gather(
        *[client.post("/webhooks/payments", content=body, headers=headers) for _ in range(20)]
    )
    assert all(r.status_code == 200 for r in results)

    balance = await client.get(f"/users/{user_id}/balance")
    assert balance.status_code == 200
    data = balance.json()
    assert data["balance"] == 50
    payment_rows = [e for e in data["recent_ledger"] if e["kind"] == "payment"]
    assert len(payment_rows) == 1
    assert payment_rows[0]["amount"] == 50
    assert payment_rows[0]["external_ref"] == payment_id
