#!/usr/bin/env bash
# API container entrypoint: migrate (no-op if current) then start uvicorn.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"${ROOT}/scripts/migrate.sh"

exec uvicorn gen_media_service.__main__:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4
