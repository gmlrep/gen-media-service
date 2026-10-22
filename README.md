# gen-media-service

Сервис генерации медиа со списанием токенов, failover провайдеров (`alpha` → `beta`), журналом операций и сторожем таймаутов, безопасным при нескольких воркерах.

## Стек

- Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, PostgreSQL
- Слоистая архитектура (`api` → `services` → `repository` → `model`) и dependency-injector
- Фейковые провайдеры (`providers/app.py`) для alpha и beta

## Быстрый старт

```bash
cp .env.example .env
docker compose up --build
```

Поднимается:

| Сервис | URL |
| --- | --- |
| API (uvicorn `--workers 4`) | http://localhost:8000 |
| Фейковый провайдер alpha | http://localhost:8101 |
| Фейковый провайдер beta | http://localhost:8102 |
| Postgres | localhost:5432 |

Проверка: `GET http://localhost:8000/health`

### Пример сценария

```bash
# Начислить пользователю 42 сто токенов (HMAC по сырому телу)
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

## Миграции

Entrypoint API перед uvicorn запускает [`scripts/migrate.sh`](scripts/migrate.sh): если `alembic current` уже показывает `(head)`, скрипт ничего не меняет; иначе выполняет `alembic upgrade head`.

Локально (Postgres запущен, заданы `.env` / `DB_*`):

```bash
uv sync
./scripts/migrate.sh
# либо принудительно:
uv run alembic upgrade head
```

Добавить следующую миграцию после изменения моделей:

```bash
uv run alembic revision --autogenerate -m "зачем меняем схему"
./scripts/migrate.sh
```

Начальная ревизия `001` также засевает каталог:

| Модель | Цена | Ноги |
| --- | --- | --- |
| `image-fast` | 2 | alpha (≤4 реф.) → beta (≤10) |
| `video-long` | 25 | beta (≤2) → alpha (≤1, `skip_on_moderation`) |

## Линт и типы

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Тесты

Нужен Postgres с применёнными миграциями (достаточно compose):

```bash
docker compose up -d postgres
uv sync
./scripts/migrate.sh
uv run pytest -q
```

GitHub Actions (`.github/workflows/ci.yml`) на каждый push/PR запускает ruff, mypy и pytest против Postgres.

Обязательное покрытие:

1. 20 одновременных одинаковых вебхуков оплаты → одно начисление
2. 10 одновременных `failed` на последней ноге → один возврат
3. Отказ первой ноги → завершение на второй, в истории две попытки
4. Поздний `completed` после сторожа → игнорируется (нет и результата, и лишнего возврата)

## «Ровно один раз» для денег

Любое изменение баланса — строка в `ledger_entry`. Колонка `balance` у пользователя обновляется **в той же транзакции**, что и INSERT.

Уникальность:

| kind | `external_ref` | Эффект |
| --- | --- | --- |
| `payment` | `payment_id` | параллельные дубликаты → `ON CONFLICT DO NOTHING` |
| `charge` | `task_id` | одно списание на задачу |
| `refund` | `task_id` | один возврат, когда все ноги отказали |

«Ровно один раз» обеспечивает уникальный constraint БД `uq_ledger_kind_ref`, а не in-memory блокировки.

## Падение процесса посреди вебхука

Если воркер упал после приёма вебхука, но до commit, провайдер (или платёжка) может повторить запрос. Повторы безопасны:

- Оплата: тот же `payment_id` нельзя вставить дважды
- Исход провайдера: принимается только попытка в статусе `waiting`; после зафиксированного перехода (`failed` / `timeout` / `succeeded`) повторные вебхуки отвечают 200 и игнорируются
- Возврат: тот же `task_id` нельзя вернуть дважды

## Правило 6 — поздний `completed` после сторожа

По истечении `PROVIDER_TIMEOUT` сторож забирает попытку через `SELECT … FOR UPDATE SKIP LOCKED`, помечает её `timeout` (как `technical`) и либо идёт на следующую ногу, либо делает единственный возврат.

Поздний `completed` по старому `external_id` возвращает HTTP 200, но **не** выставляет `result_url` и не меняет статус задачи. Уже зафиксирован переход на следующую попытку или возврат; принять поздний успех значило бы отдать и результат, и деньги. Финансовая корректность важнее опоздавшего успеха провайдера.

## Сторож при нескольких воркерах

Каждый процесс uvicorn крутит цикл сторожа. Двойная обработка исключается claim через `FOR UPDATE SKIP LOCKED` — одну попытку обрабатывает только один воркер.

## Структура проекта

```
src/gen_media_service/
  api/endpoints/     # HTTP
  services/          # биллинг, генерация, failover
  repository/        # персистентность
  model/             # SQLAlchemy
  adapters/          # HTTP-клиент провайдеров
  infrastructure/    # сторож
  core/              # config, DI, DB, lifespan
providers/           # фейковые alpha/beta
migrations/          # Alembic
tests/
```
