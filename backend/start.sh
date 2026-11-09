#!/bin/sh
set -eu

python -m alembic -c /app/alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
