#!/usr/bin/env bash
set -euo pipefail

HOST="${SERVER_HOST:-0.0.0.0}"
PORT="${SERVER_PORT:-8080}"
WORKERS="${WEB_CONCURRENCY:-2}"
THREADS="${GUNICORN_THREADS:-4}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"
KEEPALIVE="${GUNICORN_KEEPALIVE:-10}"
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"

if [[ -n "${SQLITE_PATH:-}" ]]; then
  mkdir -p "$(dirname "$SQLITE_PATH")"
fi

exec /app/.venv/bin/gunicorn server:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "${HOST}:${PORT}" \
  --workers "$WORKERS" \
  --threads "$THREADS" \
  --timeout "$TIMEOUT" \
  --keep-alive "$KEEPALIVE" \
  --access-logfile - \
  --error-logfile - \
  --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"
