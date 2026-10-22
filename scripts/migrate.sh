#!/usr/bin/env bash
# Apply Alembic migrations only when the DB is behind head.
# If already at head, exit 0 without changing anything.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f "${ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
fi

if command -v alembic >/dev/null 2>&1; then
  ALEMBIC=(alembic)
elif [[ -x "${ROOT}/.venv/bin/alembic" ]]; then
  ALEMBIC=("${ROOT}/.venv/bin/alembic")
elif [[ -f "${ROOT}/.venv/Scripts/alembic.exe" ]]; then
  ALEMBIC=("${ROOT}/.venv/Scripts/alembic.exe")
elif command -v uv >/dev/null 2>&1; then
  ALEMBIC=(uv run alembic)
else
  echo "error: alembic not found (install deps or activate .venv)" >&2
  exit 1
fi

wait_for_db() {
  local host="${DB_HOST:-localhost}"
  local port="${DB_PORT:-5432}"
  local name="${DB_NAME:-gen_media}"
  local attempts="${DB_WAIT_ATTEMPTS:-30}"
  local i

  echo "Waiting for Postgres at ${host}:${port}/${name}..."
  for i in $(seq 1 "${attempts}"); do
    # alembic current succeeds once the DB accepts connections (even with no revisions).
    if "${ALEMBIC[@]}" current >/dev/null 2>&1; then
      echo "Postgres is ready."
      return 0
    fi
    sleep 1
  done
  echo "error: Postgres did not become ready in time" >&2
  exit 1
}

wait_for_db

current_output="$("${ALEMBIC[@]}" current 2>/dev/null || true)"
if printf '%s\n' "${current_output}" | grep -q '(head)'; then
  echo "Database already up to date — nothing to do."
  echo "  ${current_output}"
  exit 0
fi

if [[ -z "${current_output//[[:space:]]/}" ]]; then
  echo "No revision applied yet — upgrading to head."
else
  echo "Database behind head (current: ${current_output}) — upgrading."
fi

"${ALEMBIC[@]}" upgrade head
echo "Migrations applied successfully."
"${ALEMBIC[@]}" current
