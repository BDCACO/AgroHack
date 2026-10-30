<div align="center">

<img src="frontend/public/favicon.svg" alt="Logo do CampoCerto" width="96">

# CampoCerto

**Gestão inteligente de insumos rurais: o estoque da fazenda dizendo o que fazer hoje.**

Feito para o **AGROHACK 2026/2, IFRO Campus Ariquemes**.

![Vue 3](https://img.shields.io/badge/Vue_3-TypeScript-42b883?logo=vuedotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.14-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?logo=postgresql&logoColor=white)
![Flutter](https://img.shields.io/badge/Flutter-Android_e_iOS-02569B?logo=flutter&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

<img src="docs/imagens/painel.png" alt="Painel do CampoCerto com os alertas do dia e quanto tempo o estoque de cada insumo dura" width="900">

</div>

Transforma registros de compras, retiradas e estoque em informação para decisão: estoque abaixo
do mínimo, risco de falta, vencimento próximo, excesso, baixa movimentação, consumo incomum e
reposição estimada, sempre com justificativa e limitações explícitas.

## O que ele faz

- **Painel do dia:** os alertas separados em urgentes, atenção e observar, cada um com a
  justificativa; quanto tempo o estoque de cada insumo dura e se acaba antes da entrega.
- **Página de cada insumo:** o gráfico do estoque ao longo do tempo, com a projeção de quando
  acaba e a reposição sugerida.
- **Compras:** sugestão do que pedir, separada por revenda, com lista de compras para o
  WhatsApp, e o acompanhamento dos pedidos até chegarem.
- **Lançamento rápido:** entradas e saídas pela tela ou por planilha do Excel ou CSV (com
  planilha modelo e prévia antes de gravar); no app, pelo leitor de código de barras.
- **Talhões e calendário de safra:** onde cada insumo foi aplicado, e um motor de análise que
  não confunde a entressafra com o ritmo da safra.
- **Relatórios** em Excel e PDF, que também servem de cópia de segurança.
- **Login com papéis** (dono e funcionário), trilha de auditoria e tema escuro.
- **App para celular** em Flutter, usando a mesma API.

## Telas

<table>
  <tr>
    <td width="50%"><img src="docs/imagens/insumo.png" alt="Página de um insumo com o gráfico do estoque e a projeção"><br><sub><b>Insumo:</b> o estoque ao longo do tempo e para onde ele vai.</sub></td>
    <td width="50%"><img src="docs/imagens/compras.png" alt="Tela de compras com a sugestão por revenda e os pedidos a caminho"><br><sub><b>Compras:</b> o que pedir hoje e os pedidos a caminho.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/imagens/movimentacoes.png" alt="Lançamento e lista de movimentações"><br><sub><b>Movimentações:</b> lançar uma saída leva segundos.</sub></td>
    <td><img src="docs/imagens/painel-escuro.png" alt="Painel no tema escuro"><br><sub><b>Tema escuro</b>, escolhido em Configurações.</sub></td>
  </tr>
  <tr>
    <td><img src="docs/imagens/configuracoes.png" alt="Configurações com aparência, calendário de safra, perfil e situação do sistema"><br><sub><b>Configurações:</b> aparência, calendário de safra, perfil e a situação do sistema.</sub></td>
    <td><img src="docs/imagens/entrar.png" alt="Tela de login"><br><sub><b>Entrar:</b> cada pessoa com o seu login e o seu papel.</sub></td>
  </tr>
</table>

<p align="center">
  <img src="docs/imagens/celular-painel.png" alt="Painel no navegador do celular, com a barra de abas embaixo" width="280"><br>
  <sub>No celular, o site vira um app com abas embaixo.</sub>
</p>

> Os prints usam a fazenda **fictícia** do `make demo` (veja [Demonstração](#demonstração)).

## Stack

| Camada | Tecnologias |
|---|---|
| Frontend | Vue 3, TypeScript, Vite, Vue Router, Pinia, Tailwind CSS v4, Axios, Apache ECharts, Plus Jakarta Sans |
| Backend | Python 3.14, FastAPI, Pydantic, SQLAlchemy 2, Alembic, openpyxl, Pytest |
| App | Flutter 3.47 (Dart 3.13), Android e iOS, pacote `http` |
| Banco | PostgreSQL 18 |
| Infra | Docker, Docker Compose |

## Pré-requisitos

- Docker com Docker Compose v2.
- Opcional, para rodar fora do container: [uv](https://docs.astral.sh/uv/) (backend) e Node 24
  (frontend).

## Como subir

```bash
cp .env.example .env        # e troque POSTGRES_PASSWORD e APP_DB_PASSWORD (só letras e números)
make up                     # banco + API + frontend
```

**Já tinha um `.env` de antes?** Acrescente uma linha, com uma senha nova (só letras e
números, 12 ou mais; gere com `openssl rand -hex 16`):

```bash
APP_DB_PASSWORD=coloqueAquiUmaSenhaNova
```

É a senha do **papel da aplicação** no PostgreSQL (`campocerto_app`), o usuário com que a API
passa a conectar: só lê e grava dados, não cria nem apaga tabela. O `POSTGRES_USER` continua
sendo o dono do banco e fica só para as migrations. O papel é criado sozinho ao subir a API,
também no banco que você já tem (nada se perde, nada a apagar); sem a linha, o `make up` para
dizendo o que falta. Detalhes em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md), seção 2, "Banco:
papéis e tempos-limite".

| Endereço | O quê |
|---|---|
| http://localhost:5173 | Aplicação |
| http://localhost:8000/api/v1/docs | Documentação interativa da API (Swagger) |
| http://localhost:8000/api/v1/health | Liveness da API |
| http://localhost:8000/api/v1/ready | API + banco |

Em **Configurações**, o cartão Sistema mostra a situação da API e do banco: é a verificação
visual de que as três partes estão conectadas.

Sem `make`? Os alvos são atalhos de `docker compose`: `docker compose up --build`.

## Login

A API tem login com dois papéis: o **dono** (tudo) e o **funcionário** (lê e lança no campo).
Em produção é obrigatório (`AUTENTICACAO=true`); no desenvolvimento fica desligado por padrão
(o app ainda não tem a tela de login). O site tem: com a autenticação ligada, ele pede o login
e esconde do funcionário o que é do dono. Para ligar:

```bash
# no .env: AUTENTICACAO=true, e então:
make up
make usuario-dono LOGIN=maria NOME="Dona Maria"   # a senha é pedida no terminal
```

O dono entra pelo site e cadastra os funcionários na tela **Usuários**. Quem pode o quê está em
[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md), "Autenticação e papéis".

## Demonstração

Sem dados reais à mão, `make demo` (com o stack no ar) cria uma fazenda **fictícia** com 6 meses
de movimentações, pensada para acender cada tipo de alerta, mais um insumo saudável para
contraste. As datas são relativas ao dia da carga: rode no dia da apresentação. A tela avisa que
são dados de demonstração, e `make demo-limpar` apaga só eles, preservando o que foi cadastrado.

Para mostrar a importação, a tela **Importar dados** oferece a planilha modelo do Excel, gerada
na hora com os insumos cadastrados; como preencher está em
[`docs/IMPORTACAO.md`](docs/IMPORTACAO.md).

## Comandos

```bash
make help       # lista tudo
make up         # sobe os serviços
make down       # derruba (os dados do banco ficam no volume)
make logs       # logs
make migrate    # alembic upgrade head
make demo       # carrega a fazenda de demonstração (fictícia, datas relativas a hoje)
make demo-limpar  # apaga só os dados de demonstração
make usuario-dono LOGIN=maria NOME="Dona Maria"   # cria o primeiro dono (pede a senha)
make test       # pytest + vitest
make lint       # ruff + vue-tsc + eslint
make check-db   # confere API ↔ PostgreSQL com o stack no ar
make verify     # lint + testes, antes de commitar
```

### Rodando fora do Docker

```bash
# Backend (precisa de um PostgreSQL; o do compose fica em 127.0.0.1:5433)
cd backend
uv sync
export ENVIRONMENT=development
# A API com o papel da aplicação, as migrations com o dono (o POSTGRES_USER):
export DATABASE_URL=postgresql+psycopg://campocerto_app:SENHA_DA_APP@127.0.0.1:5433/campocerto
export MIGRATIONS_DATABASE_URL=postgresql+psycopg://campocerto:SENHA@127.0.0.1:5433/campocerto
uv run alembic upgrade head
uv run python -m app.papel_da_aplicacao     # cria ou acerta o papel da aplicação
# --no-proxy-headers: senão o uvicorn confia no X-Forwarded-For de quem vem de 127.0.0.1
# (o proxy do Vite, um curl na própria máquina) e o IP dos limites e da trilha vira o texto dele.
uv run uvicorn app.main:app --reload --no-proxy-headers
# Só a DATABASE_URL, com o dono? Também sobe (as migrations usam a mesma), avisando no log
# que a API está com poderes de dono; em produção, ela não sobe assim.

# Frontend (o proxy aponta para localhost:8000 por padrão)
cd frontend
npm install
npm run dev
```

## App para celular

Além do site, há um app nativo para Android e iOS em Flutter, em [`mobile/`](mobile/README.md).
Usa a mesma API; o endereço dela vem do build:

```bash
cd mobile
flutter run                                                  # emulador do Android
flutter run --dart-define=API_URL=http://192.168.0.10:8000/api/v1   # celular na rede
```

Hoje tem Painel, Insumos, Movimentações e Sistema; a importação de planilha ainda é só pelo site.

## Variáveis de ambiente

Todas em `.env` na raiz; o modelo comentado está em [`.env.example`](.env.example).

| Variável | Obrigatória | Uso |
|---|---|---|
| `ENVIRONMENT` | sim | `development`, `test` ou `production`. Outro valor impede a API de subir |
| `AUTENTICACAO` | em produção | Login com papéis (dono e funcionário): `true` ou `false` (padrão). Em `production`, sem `true` a API não sobe. Ligada, crie o primeiro dono com `make usuario-dono` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | sim | Banco e o seu **dono** (superusuário do container): o compose monta com elas a `MIGRATIONS_DATABASE_URL`, usada só pelas migrations e para criar o papel da aplicação |
| `APP_DB_PASSWORD` | sim | Senha do **papel da aplicação**, com que a API conecta (`DATABASE_URL`): só letras e números, 12 ou mais. Criado e acertado sozinho a cada subida da API |
| `APP_DB_USER` | não | Nome do papel da aplicação (`campocerto_app`) |
| `DB_STATEMENT_TIMEOUT_MS`, `DB_LOCK_TIMEOUT_MS`, `DB_IDLE_IN_TRANSACTION_TIMEOUT_MS` | não | Tempos-limite da API no banco: comando (30000), espera por trava (5000) e transação parada (60000). Estourados, a API responde `503` com `Retry-After` |
| `DB_PORT`, `API_PORT`, `WEB_PORT` | não | Portas no host (5433, 8000, 5173) |
| `LOG_LEVEL` | não | Nível de log da API (`INFO`) |

## Documentação

- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md): estrutura, camadas, decisões e o que foi
  herdado do ArkoHub.
- [`docs/IMPORTACAO.md`](docs/IMPORTACAO.md): como preencher e importar a planilha de
  movimentações (Excel ou CSV), formatos aceitos e erros comuns.
- [`docs/TESTES.md`](docs/TESTES.md): o que cada suíte cobre e como rodar.
- [`docs/APRESENTACAO.md`](docs/APRESENTACAO.md): roteiro da demonstração com a fazenda fictícia.

## Estrutura

```
CampoCerto/
├── compose.yaml · Makefile · .env.example
├── backend/
│   ├── app/
│   │   ├── main.py              # create_app()
│   │   ├── core/                # config, database
│   │   ├── api/                 # router + routes/
│   │   ├── domain/              # regras de estoque puras (sem I/O)
│   │   ├── analysis/            # motor de análise: consumo, alertas, reposição
│   │   ├── schemas/             # Pydantic
│   │   └── models/              # SQLAlchemy
│   ├── migrations/              # Alembic
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── router/ layouts/ pages/ components/
│   │   ├── stores/              # Pinia
│   │   ├── services/            # Axios (cliente único em http.ts)
│   │   ├── types/
│   │   └── styles/              # Tailwind
│   └── tests/unit/
├── mobile/                  # app Flutter (Android e iOS), ver mobile/README.md
│   ├── lib/                 # core/ models/ services/ pages/ widgets/
│   └── test/
└── docs/
```
