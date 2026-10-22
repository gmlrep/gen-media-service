# gen-media-service

Token-billed media generation API with provider failover (`alpha` → `beta`), an append-only ledger, and a multi-worker-safe timeout watchdog.

## Stack

- Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL
- Layered layout (`api` → `services` → `repository` → `model`) with dependency-injector
- Fake providers (`providers/app.py`) for alpha/beta

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

This starts:

| Service | URL |
| --- | --- |
| API (uvicorn `--workers 4`) | http://localhost:8000 |
| Fake provider alpha | http://localhost:8101 |
| Fake provider beta | http://localhost:8102 |
| Postgres | localhost:5432 |

Health: `GET http://localhost:8000/health`

### Example flow

```bash
# Credit user 42 with 100 tokens (HMAC over raw body)
python - <<'PY'
import hashlib, hmac, json, urllib.request
secret = b"dev-webhook-secret"
body = json.dumps({
    "payment_id": "pay-1", "user_id": 42, "tokens": 100, "status": "succeeded"
}, separators=(",", ":")).encode()
sig = hmac.new(secret, body, hashlib.sha256).hexdigest()
req = urllib.request.Request(
    "http://localhost:8000/webhooks/payments",
    data=body,
    headers={"Content-Type": "application/json", "X-Signature": sig},
)
print(urllib.request.urlopen(req).read())
PY

curl -s http://localhost:8000/users/42/balance | jq

curl -s -X POST http://localhost:8000/generate \
  -H 'Content-Type: application/json' \
  -d '{"user_id":42,"model_slug":"image-fast","prompt":"a cat","ref_images":[]}' | jq
```

## Migrations

Compose runs `alembic upgrade head` via the `migrate` service before the API starts.

Locally (with Postgres up and `.env` set):

```bash
uv sync
uv run alembic upgrade head
```

Add the next migration after changing models:

```bash
uv run alembic revision --autogenerate -m "describe why"
uv run alembic upgrade head
```

Initial revision `001` also seeds the catalog:

| Model | Price | Legs |
| --- | --- | --- |
| `image-fast` | 2 | alpha (≤4 refs) → beta (≤10) |
| `video-long` | 25 | beta (≤2) → alpha (≤1, `skip_on_moderation`) |

## Tests

Requires Postgres with migrations applied (compose is enough):

```bash
docker compose up -d postgres migrate
uv sync
uv run pytest -q
```

Mandatory coverage:

1. 20 concurrent identical payment webhooks → one credit
2. 10 concurrent `failed` webhooks on the last leg → one refund
3. First leg fails → task finishes on second leg with two attempts
4. Late `completed` after watchdog timeout → ignored (no result + refund)

## Exactly-once money movement

Every balance change is a row in `ledger_entry`. The user `balance` column is updated in the **same transaction** as the insert.

Uniqueness:

| Kind | `external_ref` | Effect |
| --- | --- | --- |
| `payment` | `payment_id` | concurrent duplicates → `ON CONFLICT DO NOTHING` |
| `charge` | `task_id` | one debit per generation |
| `refund` | `task_id` | one credit back when all legs fail |

So “exactly once” is enforced by the database unique constraint `uq_ledger_kind_ref`, not by in-memory locks.

## Crash mid-webhook

If a worker dies after receiving a webhook but before commit, the provider (or payment system) can retry. Retries are safe:

- Payment: same `payment_id` cannot insert twice
- Provider outcome: attempt must be `waiting`; after a committed transition (`failed` / `timeout` / `succeeded`) further webhooks are acknowledged and ignored
- Refund: same `task_id` cannot refund twice

## Rule 6 — late `completed` after watchdog

When `PROVIDER_TIMEOUT` elapses, the watchdog claims the attempt with `SELECT … FOR UPDATE SKIP LOCKED`, marks it `timeout` (treated like `technical`), and advances to the next leg or performs the single refund.

A later `completed` for that attempt’s `external_id` returns HTTP 200 but **does not** set `result_url` or change task status. Reason: the service already committed either a successor attempt or a refund; accepting the late success would give the user both a result and a refund. Financial correctness wins over a late provider success.

## Multi-worker watchdog

Each uvicorn worker runs the watchdog loop. Double-processing is prevented by claiming overdue rows with `FOR UPDATE SKIP LOCKED` — only one worker can claim a given attempt.

## Project layout

```
src/gen_media_service/
  api/endpoints/     # HTTP
  services/          # billing + generation + failover
  repository/        # persistence
  model/             # SQLAlchemy
  adapters/          # provider HTTP client
  infrastructure/    # watchdog
  core/              # config, DI, DB, lifespan
providers/           # fake alpha/beta
migrations/          # Alembic
tests/
```
