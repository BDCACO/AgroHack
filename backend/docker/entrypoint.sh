#!/bin/sh
# Aplica as migrations antes de subir a API. A espera pelo banco é do compose
# (depends_on: condition: service_healthy), não deste script.
set -e

if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
  echo "Aplicando migrations (alembic upgrade head)..."
  alembic upgrade head
fi

exec "$@"
