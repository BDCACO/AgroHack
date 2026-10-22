"""Gestão de usuários (`/usuarios`), só do dono."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SENHA, CriarUsuario, entrar

USUARIOS = "/api/v1/usuarios"
EU = "/api/v1/auth/eu"


@pytest.fixture
def dono(cliente_autenticado: TestClient, criar_usuario: CriarUsuario) -> dict[str, str]:
    criar_usuario("maria", papel="dono", nome="Dona Maria")
    return entrar(cliente_autenticado, "maria")


def cadastrar(cliente: TestClient, dono: dict[str, str], **campos: object) -> dict:
    corpo = {"nome": "Zé do Trator", "login": "ze", "senha": "senha-do-ze", "papel": "funcionario"}
    resposta = cliente.post(USUARIOS, headers=dono, json=corpo | campos)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_dono_cadastra_funcionario_que_entra_com_a_senha_dada(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    ze = cadastrar(cliente_autenticado, dono, login="  Ze.Trator ")

    assert ze | {"id": 0, "criado_em": ""} == {
        "id": 0,
        "nome": "Zé do Trator",
        "login": "ze.trator",  # aparado e em minúsculas, como o login o compara
        "papel": "funcionario",
        "ativo": True,
        "criado_em": "",
        "bloqueado_ate": None,
    }
    cabecalho = entrar(cliente_autenticado, "ZE.TRATOR", "senha-do-ze")
    assert cliente_autenticado.get(EU, headers=cabecalho).json()["id"] == ze["id"]
    logins = [u["login"] for u in cliente_autenticado.get(USUARIOS, headers=dono).json()]
    assert logins == ["maria", "ze.trator"]


def test_login_repetido_sem_diferenciar_maiusculas_e_409(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    resposta = cliente_autenticado.post(
        USUARIOS,
        headers=dono,
        json={"nome": "Outra Maria", "login": "MARIA", "senha": "12345678", "papel": "dono"},
    )

    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "Já existe um usuário com esse login."


@pytest.mark.parametrize(
    "campos",
    [
        {"login": "zé"},  # acento: o mesmo login digitado em outro teclado seria outro
        {"login": "ze trator"},
        {"login": "z"},  # curto demais
        {"senha": "1234567"},  # menos de 8
        {"papel": "gerente"},
        {"nome": "   "},
        {"nome": "Zé\x00"},
    ],
)
def test_cadastro_invalido_e_422(
    cliente_autenticado: TestClient, dono: dict[str, str], campos: dict
) -> None:
    corpo = {"nome": "Zé", "login": "ze", "senha": "senha-do-ze", "papel": "funcionario"}

    resposta = cliente_autenticado.post(USUARIOS, headers=dono, json=corpo | campos)

    assert resposta.status_code == 422


def test_alterar_muda_so_o_que_veio(cliente_autenticado: TestClient, dono: dict[str, str]) -> None:
    ze = cadastrar(cliente_autenticado, dono)

    resposta = cliente_autenticado.put(
        f"{USUARIOS}/{ze['id']}", headers=dono, json={"nome": "José"}
    )
    promovido = cliente_autenticado.put(
        f"{USUARIOS}/{ze['id']}", headers=dono, json={"papel": "dono"}
    )

    assert resposta.status_code == 200, resposta.text
    assert (resposta.json()["nome"], resposta.json()["papel"]) == ("José", "funcionario")
    assert (promovido.json()["nome"], promovido.json()["papel"]) == ("José", "dono")


def test_desativar_derruba_as_sessoes_e_o_login(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    ze = cadastrar(cliente_autenticado, dono)
    do_ze = entrar(cliente_autenticado, "ze", "senha-do-ze")

    resposta = cliente_autenticado.put(
        f"{USUARIOS}/{ze['id']}", headers=dono, json={"ativo": False}
    )

    assert resposta.json()["ativo"] is False
    assert cliente_autenticado.get(EU, headers=do_ze).status_code == 401
    login = {"login": "ze", "senha": "senha-do-ze"}
    assert cliente_autenticado.post("/api/v1/auth/entrar", json=login).status_code == 401

    cliente_autenticado.put(f"{USUARIOS}/{ze['id']}", headers=dono, json={"ativo": True})
    # Reativado, entra de novo; a sessão antiga continua encerrada.
    entrar(cliente_autenticado, "ze", "senha-do-ze")
    assert cliente_autenticado.get(EU, headers=do_ze).status_code == 401


def test_ultimo_dono_ativo_nao_se_desativa_nem_vira_funcionario(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    eu = cliente_autenticado.get(EU, headers=dono).json()

    for mudanca in [{"ativo": False}, {"papel": "funcionario"}]:
        resposta = cliente_autenticado.put(f"{USUARIOS}/{eu['id']}", headers=dono, json=mudanca)

        assert resposta.status_code == 409
        assert "último dono" in resposta.json()["detail"]
    assert cliente_autenticado.get(EU, headers=dono).json()["papel"] == "dono"

    # Com outro dono ativo, pode.
    cadastrar(cliente_autenticado, dono, login="joao", papel="dono")
    resposta = cliente_autenticado.put(
        f"{USUARIOS}/{eu['id']}", headers=dono, json={"papel": "funcionario"}
    )
    assert resposta.status_code == 200, resposta.text


def test_dono_inativo_nao_conta_como_o_outro_dono(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    eu = cliente_autenticado.get(EU, headers=dono).json()
    cadastrar(cliente_autenticado, dono, login="joao", papel="dono")
    usuarios = cliente_autenticado.get(USUARIOS, headers=dono).json()
    joao = next(u for u in usuarios if u["login"] == "joao")
    cliente_autenticado.put(f"{USUARIOS}/{joao['id']}", headers=dono, json={"ativo": False})

    resposta = cliente_autenticado.put(
        f"{USUARIOS}/{eu['id']}", headers=dono, json={"ativo": False}
    )

    assert resposta.status_code == 409


def test_redefinir_a_senha_derruba_as_sessoes(
    cliente_autenticado: TestClient, dono: dict[str, str]
) -> None:
    ze = cadastrar(cliente_autenticado, dono)
    do_ze = entrar(cliente_autenticado, "ze", "senha-do-ze")

    resposta = cliente_autenticado.put(
        f"{USUARIOS}/{ze['id']}/senha", headers=dono, json={"senha_nova": "outra-senha"}
    )

    assert resposta.status_code == 204, resposta.text
    assert cliente_autenticado.get(EU, headers=do_ze).status_code == 401
    entrar(cliente_autenticado, "ze", "outra-senha")
    curta = cliente_autenticado.put(
        f"{USUARIOS}/{ze['id']}/senha", headers=dono, json={"senha_nova": "curta"}
    )
    assert curta.status_code == 422


def test_usuario_inexistente_e_404(cliente_autenticado: TestClient, dono: dict[str, str]) -> None:
    alterar = cliente_autenticado.put(f"{USUARIOS}/999", headers=dono, json={"nome": "X"})
    senha = cliente_autenticado.put(
        f"{USUARIOS}/999/senha", headers=dono, json={"senha_nova": SENHA}
    )

    assert (alterar.status_code, senha.status_code) == (404, 404)
    assert alterar.json()["detail"] == "Usuário não encontrado."
