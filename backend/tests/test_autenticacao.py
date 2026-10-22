"""Login, sessão e troca de senha (`/auth`), com a autenticação ligada."""

import hashlib
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import senha
from app.models import Sessao
from app.services import autenticacao
from tests.conftest import SENHA, CriarUsuario, entrar

ENTRAR = "/api/v1/auth/entrar"
EU = "/api/v1/auth/eu"


def test_entrar_devolve_o_token_uma_vez_e_guarda_so_o_hash(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    ze = criar_usuario("ze", nome="Zé do Trator")

    resposta = cliente_autenticado.post(
        ENTRAR, json={"login": "ze", "senha": SENHA, "dispositivo": "Celular do Zé"}
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["usuario"] == {
        "id": ze.id,
        "nome": "Zé do Trator",
        "login": "ze",
        "papel": "funcionario",
    }
    token = corpo["token"]
    assert len(token) >= 40
    sessao = db.scalar(select(Sessao))
    assert sessao.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in sessao.token_hash
    assert sessao.dispositivo == "Celular do Zé"
    # 30 dias: o app fica dias no campo sem sinal e não pode pedir a senha no meio da lida.
    expira_em = datetime.fromisoformat(corpo["expira_em"])
    assert expira_em - sessao.criada_em == timedelta(days=30)


def test_login_nao_diferencia_maiusculas_nem_espacos(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("maria", papel="dono")

    cabecalho = entrar(cliente_autenticado, "  Maria ")

    assert cliente_autenticado.get(EU, headers=cabecalho).json()["login"] == "maria"


def test_login_recusado_nao_diz_se_o_login_existe(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    criar_usuario("antigo", ativo=False)

    respostas = [
        cliente_autenticado.post(ENTRAR, json={"login": login, "senha": tentativa})
        for login, tentativa in [("ze", "senha-errada"), ("ninguem", SENHA), ("antigo", SENHA)]
    ]

    assert {r.status_code for r in respostas} == {401}
    assert len({r.text for r in respostas}) == 1
    assert respostas[0].json()["detail"].startswith("Login ou senha incorretos.")


def test_login_inexistente_gasta_o_mesmo_hash_que_o_existente(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Sem o hash, "não existe" responderia em 1 ms e "senha errada" em 200: pelo tempo, daria
    # para descobrir quais logins existem.
    criar_usuario("ze")
    conferidas: list[str] = []
    conferir = senha.conferir
    monkeypatch.setattr(
        senha,
        "conferir",
        lambda digitada, guardado: conferidas.append(guardado) or conferir(digitada, guardado),
    )

    cliente_autenticado.post(ENTRAR, json={"login": "ninguem", "senha": SENHA})
    cliente_autenticado.post(ENTRAR, json={"login": "ze", "senha": "senha-errada"})

    assert len(conferidas) == 2
    assert [c.split("$")[:4] for c in conferidas] == [["scrypt", "16384", "8", "1"]] * 2


def test_sem_token_ou_com_token_falso_e_401_com_www_authenticate(
    cliente_autenticado: TestClient,
) -> None:
    for cabecalho in [{}, {"Authorization": "Bearer inventado"}, {"Authorization": "Basic eDp5"}]:
        resposta = cliente_autenticado.get(EU, headers=cabecalho)

        assert resposta.status_code == 401
        assert resposta.headers["www-authenticate"] == "Bearer"
        assert "entre" in resposta.json()["detail"].lower()


def test_sessao_expira_em_30_dias(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, monkeypatch: pytest.MonkeyPatch
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")
    agora = datetime.now(UTC)

    monkeypatch.setattr(autenticacao, "agora", lambda: agora + timedelta(days=29, hours=23))
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200

    monkeypatch.setattr(autenticacao, "agora", lambda: agora + timedelta(days=30, minutes=1))
    resposta = cliente_autenticado.get(EU, headers=cabecalho)
    assert resposta.status_code == 401
    assert "expirou" in resposta.json()["detail"]


def test_sair_encerra_so_a_sessao_atual(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    celular, computador = entrar(cliente_autenticado, "ze"), entrar(cliente_autenticado, "ze")

    assert cliente_autenticado.post("/api/v1/auth/sair", headers=celular).status_code == 204

    resposta = cliente_autenticado.get(EU, headers=celular)
    assert resposta.status_code == 401
    assert "encerrada" in resposta.json()["detail"]
    assert cliente_autenticado.get(EU, headers=computador).status_code == 200


def test_trocar_a_senha_encerra_as_outras_sessoes(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    celular, computador = entrar(cliente_autenticado, "ze"), entrar(cliente_autenticado, "ze")

    resposta = cliente_autenticado.put(
        "/api/v1/auth/senha",
        headers=celular,
        json={"senha_atual": SENHA, "senha_nova": "nova-senha-do-ze"},
    )

    assert resposta.status_code == 204, resposta.text
    assert cliente_autenticado.get(EU, headers=celular).status_code == 200
    assert cliente_autenticado.get(EU, headers=computador).status_code == 401
    assert cliente_autenticado.post(ENTRAR, json={"login": "ze", "senha": SENHA}).status_code == 401
    entrar(cliente_autenticado, "ze", "nova-senha-do-ze")


def test_trocar_a_senha_exige_a_atual_e_8_caracteres(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    errada = cliente_autenticado.put(
        "/api/v1/auth/senha",
        headers=cabecalho,
        json={"senha_atual": "nao-e-esta", "senha_nova": "nova-senha-do-ze"},
    )
    curta = cliente_autenticado.put(
        "/api/v1/auth/senha",
        headers=cabecalho,
        json={"senha_atual": SENHA, "senha_nova": "1234567"},
    )

    assert errada.status_code == 400
    assert errada.json()["detail"] == "A senha atual não confere."
    assert curta.status_code == 422
    entrar(cliente_autenticado, "ze")  # nada mudou


def test_usuario_desativado_perde_a_sessao_na_hora(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    ze = criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    ze.ativo = False
    db.commit()

    resposta = cliente_autenticado.get(EU, headers=cabecalho)
    assert resposta.status_code == 401
    assert "desativado" in resposta.json()["detail"]


def test_auth_exige_login_mesmo_com_a_autenticacao_desligada(
    client: TestClient, criar_usuario: CriarUsuario
) -> None:
    # Desligada, nada mais exige token; mas "quem sou eu" sem token não tem resposta, e o
    # token válido é reconhecido, para o site e o app já poderem implementar o login.
    criar_usuario("ze")

    assert client.get(EU).status_code == 401
    assert client.get(EU, headers=entrar(client, "ze")).json()["login"] == "ze"
