import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app


def test_environment_e_obrigatorio(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_recusa_valor_desconhecido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "prod")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_docs_ficam_disponiveis_fora_de_producao(client: TestClient) -> None:
    assert client.get("/api/v1/docs").status_code == 200
    assert client.get("/api/v1/openapi.json").status_code == 200


def test_docs_ficam_fora_do_ar_em_producao() -> None:
    settings = Settings(environment="production", database_url="sqlite://", autenticacao=True)

    with TestClient(create_app(settings)) as c:
        assert c.get("/api/v1/docs").status_code == 404
        assert c.get("/api/v1/openapi.json").status_code == 404


def test_producao_sem_autenticacao_nao_sobe(monkeypatch: pytest.MonkeyPatch) -> None:
    # Fail-closed, como o ENVIRONMENT: esquecer a variável não pode deixar a API de
    # produção aberta a quem alcança a rede.
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("AUTENTICACAO", raising=False)

    with pytest.raises(ValidationError, match="AUTENTICACAO=true"):
        Settings(_env_file=None)
    monkeypatch.setenv("AUTENTICACAO", "false")
    with pytest.raises(ValidationError, match="AUTENTICACAO=true"):
        Settings(_env_file=None)

    monkeypatch.setenv("AUTENTICACAO", "true")
    assert Settings(_env_file=None).autenticacao is True


def test_autenticacao_desligada_por_padrao_fora_de_producao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTENTICACAO", raising=False)
    for ambiente in ["development", "test"]:
        monkeypatch.setenv("ENVIRONMENT", ambiente)

        assert Settings(_env_file=None).autenticacao is False


def test_autenticacao_recusa_valor_que_nao_e_sim_ou_nao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTENTICACAO", "talvez")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_avisa_no_log_quando_sobe_com_a_autenticacao_desligada(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        create_app(Settings(environment="test", database_url="sqlite://"))

    assert "AUTENTICACAO" in caplog.text
