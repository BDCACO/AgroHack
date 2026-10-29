"""PUT /auth/eu: o próprio nome e o próprio login, pela tela de Configurações. O login novo
pede a senha atual, e o erro conta como tentativa de login."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventoDeAuditoria
from tests.conftest import SENHA, CriarUsuario, entrar

EU = "/api/v1/auth/eu"


def test_troca_o_proprio_nome_sem_pedir_a_senha(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario, db: Session
) -> None:
    criar_usuario("ze", nome="Zé")
    cabecalho = entrar(cliente_autenticado, "ze")

    resposta = cliente_autenticado.put(EU, headers=cabecalho, json={"nome": "  José da Silva "})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {
        "id": resposta.json()["id"],
        "nome": "José da Silva",
        "login": "ze",
        "papel": "funcionario",
    }
    assert cliente_autenticado.get(EU, headers=cabecalho).json()["nome"] == "José da Silva"
    evento = db.scalars(
        select(EventoDeAuditoria).where(EventoDeAuditoria.acao == "usuario.alterado")
    ).one()
    assert evento.dados == {
        "login": "ze",
        "antes": {"nome": "Zé"},
        "depois": {"nome": "José da Silva"},
    }


def test_troca_o_login_com_a_senha_atual_e_continua_conectado(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    resposta = cliente_autenticado.put(
        EU, headers=cabecalho, json={"login": " Jose.Silva ", "senha_atual": SENHA}
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["login"] == "jose.silva"  # como o login compara
    assert cliente_autenticado.get(EU, headers=cabecalho).status_code == 200
    entrar(cliente_autenticado, "jose.silva")
    assert (
        cliente_autenticado.post(
            "/api/v1/auth/entrar", json={"login": "ze", "senha": SENHA}
        ).status_code
        == 401
    )


def test_login_novo_sem_senha_errada_ou_repetida_nao_muda_nada(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    criar_usuario("maria", papel="dono")
    cabecalho = entrar(cliente_autenticado, "ze")

    sem_senha = cliente_autenticado.put(EU, headers=cabecalho, json={"login": "jose"})
    errada = cliente_autenticado.put(
        EU, headers=cabecalho, json={"login": "jose", "senha_atual": "errada"}
    )
    repetido = cliente_autenticado.put(
        EU, headers=cabecalho, json={"login": "maria", "senha_atual": SENHA}
    )
    formato = cliente_autenticado.put(
        EU, headers=cabecalho, json={"login": "zé", "senha_atual": SENHA}
    )

    assert (sem_senha.status_code, sem_senha.json()["detail"]) == (
        400,
        "Para trocar o login, confirme com a senha atual.",
    )
    assert (errada.status_code, errada.json()["detail"]) == (400, "A senha atual não confere.")
    assert (repetido.status_code, repetido.json()["detail"]) == (
        409,
        "Já existe um usuário com esse login.",
    )
    assert formato.status_code == 422
    assert cliente_autenticado.get(EU, headers=cabecalho).json()["login"] == "ze"


def test_o_mesmo_login_nao_pede_senha_e_nome_em_branco_e_recusado(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    # O formulário manda o login de volta, sem mudança: não é troca de login.
    mesmo = cliente_autenticado.put(EU, headers=cabecalho, json={"nome": "Zé", "login": "ze"})
    branco = cliente_autenticado.put(EU, headers=cabecalho, json={"nome": "   "})

    assert mesmo.status_code == 200, mesmo.text
    assert branco.status_code == 422


def test_senha_errada_na_troca_de_login_conta_como_tentativa(
    cliente_autenticado: TestClient, criar_usuario: CriarUsuario
) -> None:
    criar_usuario("ze")
    cabecalho = entrar(cliente_autenticado, "ze")

    for _ in range(5):
        cliente_autenticado.put(EU, headers=cabecalho, json={"login": "jose", "senha_atual": "x"})

    # Bloqueado: nem a senha certa entra agora.
    certa = cliente_autenticado.put(
        EU, headers=cabecalho, json={"login": "jose", "senha_atual": SENHA}
    )
    assert certa.status_code == 400
    assert (
        cliente_autenticado.post(
            "/api/v1/auth/entrar", json={"login": "ze", "senha": SENHA}
        ).status_code
        == 401
    )


def test_sem_login_nao_se_altera_ninguem(cliente_autenticado: TestClient) -> None:
    assert cliente_autenticado.put(EU, json={"nome": "Alguém"}).status_code == 401
