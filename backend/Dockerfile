# Imagem da API. Dois alvos:
#   dev  — com dependências de desenvolvimento (pytest, ruff); usado pelo compose.
#   prod — só o runtime.
FROM python:3.14-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /bin/uv

# O venv fica FORA de /app: em desenvolvimento o código é montado em /app, e um
# venv ali dentro seria escondido pelo bind mount.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml uv.lock ./


FROM base AS dev
RUN uv sync --frozen
COPY --chown=app:app . .
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
# Sem o log de acesso do uvicorn: a API escreve o dela (app/api/protecoes.py), uma linha
# por pedido com o X-Request-ID e o usuário, e sem a query string, que o do uvicorn leva.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--no-access-log"]


FROM base AS prod
RUN uv sync --frozen --no-dev
COPY --chown=app:app . .
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header", "--no-access-log"]
