#!/bin/sh
# Prepara o banco antes de subir a API, como o DONO do schema (MIGRATIONS_DATABASE_URL):
# aplica as migrations e garante o papel da aplicação, o usuário sem poder de DDL com que
# a API conecta (DATABASE_URL). Nessa ordem: no banco novo, as tabelas já existem quando
# as permissões são dadas. A espera pelo banco é do compose (depends_on: condition:
# service_healthy), não deste script.
set -e

if [ "${RUN_MIGRATIONS_ON_START:-true}" = "true" ]; then
  echo "Aplicando migrations (alembic upgrade head)..."
  alembic upgrade head
  echo "Garantindo o papel da aplicação no banco..."
  python -m app.papel_da_aplicacao
fi

# A API não precisa da senha do dono: sem isto, quem achasse uma falha nela a leria do
# ambiente do processo. Os outros comandos (alembic, demonstração) seguem com ela.
case "$1" in
  uvicorn) unset MIGRATIONS_DATABASE_URL ;;
esac

exec "$@"
