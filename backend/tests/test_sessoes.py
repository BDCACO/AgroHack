"""As sessões abertas de cada um: onde há login, o último uso, a validade que se renova
com o uso, e encerrar um aparelho sem derrubar os outros (o celular perdido)."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Sessao
from tests.conftest import SENHA, CriarUsuario

ENTRAR = "/api/v1/auth/entrar"


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
