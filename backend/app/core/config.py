"""Configuração centralizada, validada no boot.

Toda variável de ambiente que a API consome é declarada aqui, e só aqui. Faltou
variável obrigatória? A aplicação não sobe — melhor falhar no deploy do que
descobrir em produção que o banco era o default de alguém.
"""

from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
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
    database_url: str

    log_level: str = "INFO"

    # Login com papéis (dono e funcionário). Desligada, ninguém precisa de token, como
    # antes do login existir: é o padrão em development e test, para o site e o app que
    # ainda não têm tela de login continuarem funcionando. Em produção é obrigatória.
    autenticacao: bool = False

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
    def docs_habilitadas(self) -> bool:
        """/docs e /openapi.json ficam fora do ar em produção."""
        return self.environment != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # campos obrigatórios vêm do ambiente
