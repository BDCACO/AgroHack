"""O limite de 8 MB do corpo conta os bytes que chegam, e não só o `Content-Length`: um
pedido `Transfer-Encoding: chunked` não traz o tamanho e, sem a conta, iria inteiro para a
memória. A prova com o uvicorn de verdade está em
tests/integracao/test_blindagem_da_api.py."""

import json
from collections.abc import Iterator

import anyio
from fastapi.testclient import TestClient

from app.main import CORPO_MAXIMO

PEDACO = 64 * 1024
FRASE = "Arquivo grande demais: o máximo é 5 MB."


def test_corpo_sem_content_length_acima_do_limite_e_413(client: TestClient) -> None:
    def pedacos() -> Iterator[bytes]:
        for _ in range(CORPO_MAXIMO // PEDACO + 20):
            yield b" " * PEDACO

    resposta = client.post(
        "/api/v1/importacoes", content=pedacos(), headers={"content-type": "application/json"}
    )

    assert resposta.status_code == 413
    assert resposta.json() == {"detail": FRASE}
    assert "X-Request-ID" in resposta.headers


def test_corpo_sem_content_length_dentro_do_limite_passa(client: TestClient) -> None:
    corpo = json.dumps({"conteudo": "data;insumo;tipo;quantidade\n"})

    def pedacos() -> Iterator[bytes]:
        yield corpo.encode()

    resposta = client.post(
        "/api/v1/importacoes", content=pedacos(), headers={"content-type": "application/json"}
    )

    assert resposta.status_code == 200, resposta.text


def test_para_de_ler_logo_depois_do_limite(client: TestClient) -> None:
    """Pelo ASGI direto, com o corpo chegando em pedaços como pelo uvicorn: a API recusa
    assim que passa de 8 MB e não pede o resto (o TestClient juntaria tudo antes)."""
    total = CORPO_MAXIMO // PEDACO * 4  # uns 32 MB oferecidos
    lidos = 0
    respostas: list[dict] = []

    async def receber() -> dict:
        nonlocal lidos
        lidos += 1
        return {"type": "http.request", "body": b" " * PEDACO, "more_body": lidos < total}

    async def enviar(mensagem: dict) -> None:
        respostas.append(mensagem)

    escopo = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/importacoes",
        "raw_path": b"/api/v1/importacoes",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"transfer-encoding", b"chunked")],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    anyio.run(client.app, escopo, receber, enviar)

    assert respostas[0]["status"] == 413
    assert lidos <= CORPO_MAXIMO // PEDACO + 1


def test_content_length_acima_do_limite_continua_recusado_antes_de_ler(
    client: TestClient,
) -> None:
    resposta = client.post(
        "/api/v1/importacoes",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": "50000000"},
    )

    assert resposta.status_code == 413
    assert resposta.json() == {"detail": FRASE}
