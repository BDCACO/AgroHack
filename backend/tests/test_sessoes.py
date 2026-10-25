"""As sessões abertas de cada um: onde há login, o último uso, a validade que se renova
com o uso, e encerrar um aparelho sem derrubar os outros (o celular perdido)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.models import Sessao
from app.services import autenticacao
from tests.conftest import SENHA, CriarUsuario, entrar

ENTRAR = "/api/v1/auth/entrar"
EU = "/api/v1/auth/eu"


def test_login_guarda_o_ip_e_o_ultimo_uso(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    criar_usuario("ze")

    resposta = cliente_autenticado.post(
        ENTRAR, json={"login": "ze", "senha": SENHA, "dispositivo": "Celular do Zé"}
    )

    assert resposta.status_code == 200, resposta.text
    sessao = db.scalar(select(Sessao))
    # O mesmo critério da auditoria: o endereço que o servidor viu (o TestClient se chama
    # "testclient"), e nunca o X-Forwarded-For, que qualquer um escreve.
    assert sessao.ip == "testclient"
    assert sessao.ultimo_uso_em == sessao.criada_em


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> Callable[..., datetime]:
    """Põe o relógio do serviço no instante pedido (dias e minutos depois do início),
    sem dormir, como os testes do bloqueio."""
    inicio = datetime.now(UTC)

    def ajustar(**depois: float) -> datetime:
        momento = inicio + timedelta(**depois)
        monkeypatch.setattr(autenticacao, "agora", lambda: momento)
        return momento

    ajustar()
    return ajustar


def _gravacoes_na_sessao(db: Session) -> list[str]:
    """Os UPDATE em `sessoes` que chegam ao banco a partir de agora."""
    gravacoes: list[str] = []

    def anotar(_conexao: object, _cursor: object, comando: str, *_: object) -> None:
        if comando.lstrip().upper().startswith("UPDATE SESSOES"):
            gravacoes.append(comando)

    event.listen(db.get_bind(), "before_cursor_execute", anotar)
    return gravacoes


def test_ultimo_uso_e_anotado_a_cada_5_minutos_e_nao_a_cada_pedido(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    db: Session,
    relogio: Callable[..., datetime],
) -> None:
    criar_usuario("ze")
    login = relogio()
    cabecalho = entrar(cliente_autenticado, "ze")
    sessao = db.scalar(select(Sessao))
    gravacoes = _gravacoes_na_sessao(db)

    # Um pedido atrás do outro (o Painel abre vários de uma vez) não grava nada.
    for minutos in (0, 1, 4, 4.99):
        relogio(minutes=minutos)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert gravacoes == []
    db.refresh(sessao)
    assert sessao.ultimo_uso_em == login

    # Passados 5 minutos do último registro, o pedido seguinte anota o uso e renova a
    # validade: 30 dias a partir dele.
    usado = relogio(minutes=5)
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert len(gravacoes) == 1
    db.refresh(sessao)
    assert sessao.ultimo_uso_em == usado
    assert sessao.expira_em == usado + timedelta(days=30)

    relogio(minutes=9)
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    assert len(gravacoes) == 1


def test_quem_usa_nao_e_derrubado_no_30o_dia(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, relogio: Callable[..., datetime]
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    for dia in (10, 29, 45, 70):
        relogio(days=dia)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200, dia


def test_nem_quem_usa_passa_de_90_dias_sem_entrar_de_novo(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    db: Session,
    relogio: Callable[..., datetime],
) -> None:
    # O teto: um token copiado não vive para sempre só porque alguém o usa, e a senha é
    # pedida de novo de tempos em tempos.
    criar_usuario("ze")
    login = relogio()
    cabecalho = entrar(cliente_autenticado, "ze")

    for dia in (20, 40, 60, 80, 89):
        relogio(days=dia)
        assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200, dia
    sessao = db.scalar(select(Sessao))
    assert sessao.expira_em == login + timedelta(days=90)

    relogio(days=90, minutes=1)
    resposta = cliente_autenticado.get(EU, headers=cabecalho)
    assert resposta.status_code == 401
    assert "expirou" in resposta.json()["detail"]
