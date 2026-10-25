"""Configuração centralizada, validada no boot.

Toda variável de ambiente que a API consome é declarada aqui, e só aqui. Faltou
variável obrigatória? A aplicação não sobe — melhor falhar no deploy do que
descobrir em produção que o banco era o default de alguém.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CampoCerto API"
    api_v1_prefix: str = "/api/v1"

    # Sem default, de propósito (padrão herdado do ArkoHub): um erro de digitação
    # no NOME da variável não pode fazer a API subir silenciosamente como
    # "development" em produção.
    environment: Literal["development", "test", "production"]

    # Sem default também: não existe banco "padrão" aceitável.
    # Formato: postgresql+psycopg://usuario:senha@host:5432/banco
    # É a conexão da API, com o papel da aplicação: lê e grava dados, e só (ver
    # app/papel_da_aplicacao.py). Em produção, conectada como superusuário ou como dona
    # das tabelas, a API não sobe.
    database_url: str
    # A do dono do schema, só para o Alembic (DDL) e para garantir o papel da aplicação.
    # Sem ela, vale a DATABASE_URL: no desenvolvimento com um papel só, nada a configurar.
    migrations_database_url: str | None = None

    # Tempos-limite da conexão da API com o PostgreSQL. Sem eles, uma consulta presa, um
    # `FOR UPDATE` esperando trava (login, recebimento de pedido) ou uma transação esquecida
    # aberta seguram a conexão e as travas para sempre, e a API fica pendurada. Zero, no
    # PostgreSQL, desliga o limite: por isso só valores positivos.
    # Consulta: o maior comando medido (gravar a importação de 50 mil linhas, o máximo de
    # uma planilha, e o relatório com elas) levou menos de 1 s; 30 s dão folga para o banco
    # crescer anos sem cortar o normal.
    db_statement_timeout_ms: int = Field(default=30_000, gt=0)
    # Espera por trava: nenhuma trava legítima dura mais que uma requisição curta. Cinco
    # segundos e o pedido desiste com "tente de novo", em vez de fila sem fim.
    db_lock_timeout_ms: int = Field(default=5_000, gt=0)
    # Transação aberta sem falar com o banco: a maior pausa medida foi a da importação de 50
    # mil linhas (uns 7 s de Python lendo a planilha); o relatório monta o Excel depois de
    # terminar a leitura. Um minuto só derruba a transação esquecida.
    db_idle_in_transaction_timeout_ms: int = Field(default=60_000, gt=0)
    # Espera por uma conexão livre no pool, em segundos.
    db_pool_timeout_s: float = Field(default=10, gt=0)

    log_level: str = "INFO"

    # Login com papéis (dono e funcionário). Desligada, ninguém precisa de token, como
    # antes do login existir: é o padrão em development e test, para o site e o app que
    # ainda não têm tela de login continuarem funcionando. Em produção é obrigatória.
    autenticacao: bool = False

    # HSTS: o navegador passa a só usar HTTPS com este endereço, por tantos segundos. Zero
    # (o padrão) não manda o cabeçalho: no desenvolvimento em http://, ligado, o navegador
    # recusaria o http://localhost de todos os projetos até o prazo vencer. Ligar só com
    # HTTPS na frente da API (um ano: 31536000).
    hsts_segundos: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _producao_exige_autenticacao(self) -> Self:
        # Fail-closed, como o ENVIRONMENT: esquecer a variável não pode deixar a API de
        # produção aberta a quem alcança a rede. Ligar é decisão explícita, desligar não
        # existe em produção.
        if self.environment == "production" and not self.autenticacao:
            raise ValueError(
                "em production, a API só sobe com AUTENTICACAO=true (login com papéis). "
                "Crie o primeiro dono com `python -m app.usuarios criar-dono`."
            )
        return self

    @property
    def url_das_migrations(self) -> str:
        return self.migrations_database_url or self.database_url

    @property
    def docs_habilitadas(self) -> bool:
        """/docs e /openapi.json ficam fora do ar em produção."""
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # campos obrigatórios vêm do ambiente
