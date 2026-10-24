.DEFAULT_GOAL := help
.PHONY: help up down logs migrate demo demo-limpar usuario-dono test test-backend test-frontend test-integracao lint check-db verify

COMPOSE := docker compose
# Testes e lint rodam DENTRO do container (padrão do ArkoHub): a máquina não
# precisa de Python nem Node instalados. Sem cache em disco: o código é
# montado do host e o usuário do container não deve sujar a árvore.
API_RUN := $(COMPOSE) run --rm --no-deps -e ENVIRONMENT=test -e DATABASE_URL=sqlite:// \
  -e RUN_MIGRATIONS_ON_START=false api
WEB_RUN := $(COMPOSE) run --rm --no-deps web

help: ## Lista os alvos disponíveis
	@grep -hE '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*##/ ##/' | sort | awk 'BEGIN{FS="##"}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Sobe banco, API (:8000) e frontend (:5173)
	$(COMPOSE) up --build

down: ## Derruba os serviços (os dados do banco ficam no volume)
	$(COMPOSE) down

logs: ## Acompanha os logs de todos os serviços
	$(COMPOSE) logs -f

migrate: ## Aplica as migrations (alembic upgrade head)
	$(COMPOSE) run --rm api alembic upgrade head

demo: ## Carrega a fazenda de demonstração (fictícia, datas relativas a hoje; substitui a anterior)
	$(COMPOSE) run --rm api python -m app.demo carregar

demo-limpar: ## Apaga só os dados de demonstração
	$(COMPOSE) run --rm api python -m app.demo limpar

# A senha é pedida no terminal (duas vezes, sem aparecer); para automação, SENHA_DO_DONO.
usuario-dono: ## Cria o primeiro dono: make usuario-dono LOGIN=maria NOME="Dona Maria"
	@test -n "$(LOGIN)" -a -n "$(NOME)" || { echo 'uso: make usuario-dono LOGIN=maria NOME="Dona Maria"'; exit 2; }
	$(COMPOSE) run --rm -e SENHA_DO_DONO api python -m app.usuarios criar-dono --login "$(LOGIN)" --nome "$(NOME)"

test-backend: ## Pytest da API (SQLite em memória, sem banco)
	$(API_RUN) pytest -p no:cacheprovider

test-frontend: ## Vitest do frontend
	$(WEB_RUN) sh -c "npm install --no-audit --no-fund && npm test"

# Num banco à parte (campocerto_teste), criado na hora: o schema dele é apagado a cada rodada.
# Com a URL do dono (as migrations e o preparo de cada teste); a API dos testes sobe com um
# papel da aplicação próprio (campocerto_app_teste), criado pela suíte.
test-integracao: ## API real (uvicorn) + PostgreSQL real, por HTTP (exige `make up` rodando)
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -tAc "select 1 from pg_database where datname = '"'"'campocerto_teste'"'"'" | grep -q 1 || createdb -U "$$POSTGRES_USER" campocerto_teste'
	$(COMPOSE) exec api sh -c 'INTEGRACAO_DATABASE_URL="$${MIGRATIONS_DATABASE_URL%/*}/campocerto_teste" pytest -p no:cacheprovider tests/integracao'

test: test-backend test-frontend ## Todos os testes unitários

lint: ## ruff + vue-tsc + eslint
	$(API_RUN) ruff check --no-cache .
	$(API_RUN) ruff format --no-cache --check .
	$(WEB_RUN) sh -c "npm install --no-audit --no-fund && npm run typecheck && npm run lint"

check-db: ## Confere a cadeia real API → PostgreSQL (exige `make up` rodando)
	curl -fsS http://127.0.0.1:$${API_PORT:-8000}/api/v1/ready && echo
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB" -tAc "select version_num from alembic_version"'
	@# Com quem a API conecta: o papel da aplicação (campocerto_app), e não o dono.
	$(COMPOSE) exec api python -c "from sqlalchemy import text; from app.core.database import get_engine; print(get_engine().connect().scalar(text('select current_user')))"

verify: lint test ## Tudo que precisa passar antes de um commit
