"""Cada pedido com um identificador (`X-Request-ID`) e uma linha de log de acesso, para o
produtor informar ao suporte o código do erro e quem cuida do servidor achar o pedido no
log. A linha leva só o que serve para isso: nunca corpo, token, senha ou query string."""

import json
import logging
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.conftest import SENHA, CriarUsuario, entrar


def linhas_de_acesso(caplog: pytest.LogCaptureFixture) -> list[dict]:
    return [json.loads(r.getMessage()) for r in caplog.records if r.name == "app.acesso"]


def log_do_servidor(caplog: pytest.LogCaptureFixture) -> str:
    """O que a API escreveu no log (o `httpx` do TestClient também loga, do lado do cliente)."""
    return "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("app"))


def test_toda_resposta_leva_um_id_novo(client: TestClient) -> None:
    primeira = client.get("/api/v1/health")
    segunda = client.get("/api/v1/health")

    assert UUID(primeira.headers["X-Request-ID"])
    assert primeira.headers["X-Request-ID"] != segunda.headers["X-Request-ID"]


@pytest.mark.parametrize(
    "id_do_cliente", ["3f2b8c1e-9d4a-4f6b-8e2a-1c5d7e9f0a3b", "fila-do-app_42", "A" * 64]
)
def test_id_do_cliente_em_formato_seguro_e_mantido(client: TestClient, id_do_cliente: str) -> None:
    # O app pode mandar o seu, e o mesmo id aparece no celular e no log do servidor.
    resposta = client.get("/api/v1/health", headers={"X-Request-ID": id_do_cliente})

    assert resposta.headers["X-Request-ID"] == id_do_cliente


@pytest.mark.parametrize(
    "id_do_cliente",
    [b"com espaco", b"x" * 65, b"id;rm -rf", b"a\tb", "ação".encode(), b"<script>", b""],
)
def test_id_do_cliente_fora_do_formato_e_trocado_por_um_novo(
    client: TestClient, caplog: pytest.LogCaptureFixture, id_do_cliente: bytes
) -> None:
    # O id vai para o log e para um cabeçalho da resposta: texto livre ali permitiria forjar
    # linhas no log ou cabeçalhos na resposta.
    with caplog.at_level(logging.INFO, logger="app.acesso"):
        resposta = client.get("/api/v1/health", headers={"X-Request-ID": id_do_cliente})

    devolvido = resposta.headers["X-Request-ID"]
    assert devolvido.encode() != id_do_cliente
    assert UUID(devolvido)
    [linha] = linhas_de_acesso(caplog)
    assert linha["id"] == devolvido


def test_log_de_acesso_uma_linha_por_pedido_sem_a_query_string(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="app.acesso"):
        resposta = client.get("/api/v1/movimentacoes?busca=segredo-da-busca&limite=5")

    [linha] = linhas_de_acesso(caplog)
    assert linha == {
        "id": resposta.headers["X-Request-ID"],
        "metodo": "GET",
        "caminho": "/api/v1/movimentacoes",
        "status": 200,
        "duracao_ms": linha["duracao_ms"],
        "usuario_id": None,
        "ip": "testclient",
    }
    assert isinstance(linha["duracao_ms"], float)
    assert linha["duracao_ms"] >= 0
    assert "segredo-da-busca" not in log_do_servidor(caplog)


def test_log_de_acesso_leva_o_usuario_e_nunca_senha_token_nem_corpo(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    maria = criar_usuario("maria", "dono")

    with caplog.at_level(logging.INFO):
        cabecalho = entrar(cliente_autenticado, "maria")
        cliente_autenticado.get("/api/v1/auth/eu", headers=cabecalho)
        cliente_autenticado.post(
            "/api/v1/auth/entrar", json={"login": "maria", "senha": "errada-de-proposito"}
        )
        cliente_autenticado.post(
            "/api/v1/insumos", headers=cabecalho, json={"nome": "Insumo-secreto", "unidade": "kg"}
        )

    linhas = linhas_de_acesso(caplog)
    assert [(linha["metodo"], linha["status"]) for linha in linhas] == [
        ("POST", 200),
        ("GET", 200),
        ("POST", 401),
        ("POST", 201),
    ]
    assert [linha["usuario_id"] for linha in linhas] == [maria.id, maria.id, None, maria.id]
    token = cabecalho["Authorization"].removeprefix("Bearer ")
    for segredo in (token, SENHA, "errada-de-proposito", "Insumo-secreto"):
        assert segredo not in log_do_servidor(caplog)
