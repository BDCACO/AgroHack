"""A blindagem da API contra o uvicorn de verdade, por HTTP: o limite de tentativas de login
e de escritas por IP (429 com Retry-After), o limite de 8 MB do corpo contando os bytes que
chegam (o pedido chunked, sem Content-Length, que o TestClient não manda de verdade), os
cabeçalhos de segurança e o X-Request-ID em respostas reais, e o que não pode quebrar: o
Swagger em desenvolvimento, a importação de 5 MB e o download do Excel.

Cada teste sobe o seu uvicorn, com o limite por IP ligado nos números padrão (os outros
arquivos o desligam, porque todos os testes vêm de 127.0.0.1): a contagem começa do zero."""

import base64
import io
import secrets
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from openpyxl import Workbook
from sqlalchemy import Engine, text

from app.core.relogio import hoje
from tests.integracao.conftest import _banco_vazio, subir_uvicorn
from tests.integracao.test_banco_privilegio_e_tempos import segurar
from tests.integracao.test_fluxo_autenticacao import SENHA_DO_DONO, criar_dono

PEDACO = 64 * 1024
CORPO_MAXIMO = 8_000_000
FIXOS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "cross-origin-resource-policy": "same-origin",
    "cache-control": "no-store",
}
CSP_DA_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


@pytest.fixture
def blindada(banco: Engine) -> Iterator[httpx.Client]:
    """O login ligado, o limite por IP ligado e um lock_timeout curto (para o 503 real não
    levar os 5 s do padrão), com o banco vazio e a dona Maria criada pelo comando."""
    _banco_vazio(banco)
    criado = criar_dono("maria", "Dona Maria")
    assert criado.returncode == 0, criado.stderr
    servidor = subir_uvicorn(AUTENTICACAO="true", LIMITE_POR_IP="true", DB_LOCK_TIMEOUT_MS="500")
    base = next(servidor)
    try:
        with httpx.Client(base_url=base, timeout=60) as cliente:
            yield cliente
    finally:
        servidor.close()


def entrar(api: httpx.Client, login: str = "maria", senha: str = SENHA_DO_DONO) -> httpx.Response:
    return api.post("/auth/entrar", json={"login": login, "senha": senha})


def token(api: httpx.Client) -> dict[str, str]:
    resposta = entrar(api)
    assert resposta.status_code == 200, resposta.text
    return {"Authorization": f"Bearer {resposta.json()['token']}"}


def conferir_a_blindagem(resposta: httpx.Response) -> None:
    for nome, valor in FIXOS.items():
        assert resposta.headers[nome] == valor, (nome, resposta.status_code)
    assert resposta.headers["x-request-id"]
    assert "strict-transport-security" not in resposta.headers


def eventos(banco: Engine, acao: str) -> list[Any]:
    with banco.connect() as conexao:
        return list(
            conexao.execute(
                text("SELECT ip, dados FROM eventos_de_auditoria WHERE acao = :acao ORDER BY id"),
                {"acao": acao},
            )
        )


def test_login_limitado_por_ip_sem_barrar_o_produtor(blindada: httpx.Client, banco: Engine) -> None:
    api = blindada
    # O produtor erra três vezes e entra.
    assert [entrar(api, senha="senha-errada").status_code for _ in range(3)] == [401] * 3
    entrou = entrar(api)
    assert entrou.status_code == 200
    da_maria = {"Authorization": f"Bearer {entrou.json()['token']}"}
    # Mais seis tentativas (num login que não existe) fecham as 10 do minuto.
    assert [entrar(api, "fulano").status_code for _ in range(6)] == [401] * 6

    limitado = entrar(api)

    assert limitado.status_code == 429
    assert 1 <= int(limitado.headers["retry-after"]) <= 60
    assert limitado.json()["detail"] == (
        "Muitas tentativas de entrar a partir desta rede. Espere 1 minuto e tente de novo."
    )
    conferir_a_blindagem(limitado)
    # Insistir continua 429, sem contar como erro da Maria e sem um evento por tentativa.
    assert {entrar(api, senha="senha-errada").status_code for _ in range(10)} == {429}
    with banco.connect() as conexao:
        falhas, bloqueado = conexao.execute(
            text("SELECT falhas_seguidas, bloqueado_ate FROM usuarios WHERE login = 'maria'")
        ).one()
    assert (falhas, bloqueado) == (0, None)
    assert len(eventos(banco, "login.recusado")) == 3
    [(ip, dados)] = eventos(banco, "login.limitado")
    assert ip == "127.0.0.1"
    assert (dados["limite"], dados["janela_segundos"]) == (10, 60)
    # As sessões já abertas continuam: o limite é só de quem tenta entrar.
    eu = api.get("/auth/eu", headers=da_maria)
    assert eu.status_code == 200
    assert eu.json()["login"] == "maria"


def test_outro_ip_continua_entrando(blindada: httpx.Client) -> None:
    for _ in range(11):
        entrar(blindada, "fulano")
    assert entrar(blindada).status_code == 429

    # Outro endereço de origem, no mesmo computador: 127.0.0.2 também é a própria máquina.
    transporte = httpx.HTTPTransport(local_address="127.0.0.2")
    try:
        with httpx.Client(base_url=blindada.base_url, transport=transporte) as outro:
            assert entrar(outro).status_code == 200
    except httpx.ConnectError as erro:  # pragma: no cover — sistema sem 127.0.0.2
        pytest.skip(f"este sistema não deixa usar 127.0.0.2 como origem: {erro}")


def test_escritas_limitadas_por_ip_e_leituras_livres(blindada: httpx.Client) -> None:
    api = blindada
    dono = token(api)

    respostas = [api.delete("/movimentacoes/999999", headers=dono) for _ in range(121)]

    assert [r.status_code for r in respostas] == [404] * 120 + [429]
    assert 1 <= int(respostas[-1].headers["retry-after"]) <= 60
    conferir_a_blindagem(respostas[-1])
    assert {api.get("/insumos", headers=dono).status_code for _ in range(30)} == {200}


def test_corpo_chunked_acima_de_8mb_e_413_sem_derrubar_o_servidor(
    blindada: httpx.Client,
) -> None:
    api = blindada
    dono = token(api)
    oferecidos = 0

    def pedacos() -> Iterator[bytes]:
        nonlocal oferecidos
        for _ in range(CORPO_MAXIMO // PEDACO * 2):  # uns 16 MB
            oferecidos += PEDACO
            yield b" " * PEDACO

    resposta = api.post(
        "/importacoes",
        content=pedacos(),
        headers=dono | {"content-type": "application/json"},
    )

    assert resposta.request.headers.get("transfer-encoding") == "chunked"
    assert "content-length" not in resposta.request.headers
    assert resposta.status_code == 413
    assert resposta.json() == {"detail": "Arquivo grande demais: o máximo é 5 MB."}
    conferir_a_blindagem(resposta)
    # O servidor continua de pé e atendendo.
    assert api.get("/health").json() == {"status": "ok"}
    assert api.get("/insumos", headers=dono).status_code == 200


def planilha_de_5mb() -> bytes:
    """Uma planilha válida de quase 5 MB, o maior arquivo que a tela aceita: as
    movimentações de verdade, mais uma aba de anotações com texto que não comprime."""
    livro = Workbook()
    aba = livro.active
    aba.title = "Movimentações"
    aba.append(["data", "insumo", "unidade", "tipo", "quantidade"])
    for numero in range(1, 201):
        aba.append([hoje(), f"Insumo {numero % 7}", "kg", "entrada", numero])
    notas = livro.create_sheet("Anotações")
    for _ in range(4_350):  # uns 1,12 KB cada, comprimidos: quase 4,9 MB
        notas.append([secrets.token_urlsafe(1_100)])
    arquivo = io.BytesIO()
    livro.save(arquivo)
    return arquivo.getvalue()


def test_importacao_de_5mb_continua_passando(blindada: httpx.Client) -> None:
    api = blindada
    dono = token(api)
    planilha = planilha_de_5mb()
    xlsx = base64.b64encode(planilha).decode()
    assert 4_500_000 < len(planilha) <= 5_000_000
    assert len(xlsx) > 6_000_000

    previa = api.post("/importacoes", headers=dono, json={"xlsx": xlsx})
    assert previa.status_code == 200, previa.text[:500]
    assert previa.json()["erros"] == []

    # A mesma, mandada em pedaços (sem Content-Length): o limite conta e deixa passar.
    corpo = f'{{"xlsx": "{xlsx}", "confirmar": true}}'.encode()

    def pedacos() -> Iterator[bytes]:
        for inicio in range(0, len(corpo), PEDACO):
            yield corpo[inicio : inicio + PEDACO]

    gravada = api.post(
        "/importacoes", headers=dono | {"content-type": "application/json"}, content=pedacos()
    )
    assert gravada.status_code == 200, gravada.text[:500]
    assert gravada.json()["linhas"] == 200
    assert len(api.get("/movimentacoes", headers=dono).json()) == 200


def test_cabecalhos_e_id_em_respostas_reais(blindada: httpx.Client, banco: Engine) -> None:
    api = blindada
    dono = token(api)
    api.post("/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"})

    respostas = {
        "json": api.get("/insumos", headers=dono),
        "401": api.get("/insumos"),
        "404": api.get("/insumos/999999", headers=dono),
        "422": api.post("/insumos", headers=dono, json={"nome": ""}),
        "413": api.post(
            "/importacoes",
            headers=dono | {"content-type": "application/json"},
            content=b" " * (CORPO_MAXIMO + 1),
        ),
        "excel": api.get("/relatorio.xlsx", headers=dono),
    }

    for nome, resposta in respostas.items():
        conferir_a_blindagem(resposta)
        assert resposta.headers["content-security-policy"] == CSP_DA_API, nome
    assert [respostas[n].status_code for n in ("json", "401", "404", "422", "413")] == [
        200,
        401,
        404,
        422,
        413,
    ]
    excel = respostas["excel"]
    assert excel.status_code == 200
    assert excel.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert excel.headers["content-disposition"].startswith("attachment; filename=")
    assert excel.content.startswith(b"PK")
    ids = {r.headers["x-request-id"] for r in respostas.values()}
    assert len(ids) == len(respostas)

    # O id do app volta igual; o que não é seguro vira outro.
    assert api.get("/health", headers={"X-Request-ID": "fila-42"}).headers["x-request-id"] == (
        "fila-42"
    )
    trocado = api.get("/health", headers={"X-Request-ID": "x" * 65}).headers["x-request-id"]
    assert trocado != "x" * 65

    # Um 5xx de verdade: a linha da Maria presa por outra conexão, o login desiste no
    # lock_timeout e responde 503 com o id no corpo e nos cabeçalhos.
    soltar = threading.Event()
    linha = segurar(banco, "SELECT 1 FROM usuarios WHERE login = 'maria' FOR UPDATE", soltar)
    try:
        comeco = time.perf_counter()
        ocupado = entrar(api)
    finally:
        soltar.set()
        linha.join()
    assert time.perf_counter() - comeco < 5
    assert ocupado.status_code == 503
    assert ocupado.headers["retry-after"] == "5"
    assert ocupado.json()["id_da_requisicao"] == ocupado.headers["x-request-id"]
    conferir_a_blindagem(ocupado)


def test_swagger_abre_em_desenvolvimento(blindada: httpx.Client) -> None:
    docs = blindada.get("/docs")
    esquema = blindada.get("/openapi.json")

    assert docs.status_code == 200
    assert "swagger-ui" in docs.text
    csp = docs.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in csp
    assert "'sha256-" in csp
    assert docs.headers["x-frame-options"] == "DENY"
    assert esquema.status_code == 200
    assert esquema.json()["info"]["title"] == "CampoCerto API"


def test_x_forwarded_for_forjado_nao_troca_o_ip(blindada: httpx.Client, banco: Engine) -> None:
    # O uvicorn, vindo de 127.0.0.1, confiaria no X-Forwarded-For e trocaria o IP do cliente
    # pelo texto do cabeçalho, se não subisse com --no-proxy-headers: trocá-lo a cada pedido
    # zeraria os limites e forjaria o IP na trilha e na sessão.
    api = blindada

    def forjado(numero: int) -> dict[str, str]:
        return {"X-Forwarded-For": f"203.0.113.{numero}"}

    entrou = api.post(
        "/auth/entrar", json={"login": "maria", "senha": SENHA_DO_DONO}, headers=forjado(1)
    )
    assert entrou.status_code == 200, entrou.text
    dono = {"Authorization": f"Bearer {entrou.json()['token']}"}
    errou = api.post(
        "/auth/entrar", json={"login": "maria", "senha": "senha-errada"}, headers=forjado(2)
    )
    assert errou.status_code == 401
    tentativas = [
        api.post(
            "/auth/entrar",
            json={"login": "fulano", "senha": "senha-errada"},
            headers=forjado(numero),
        ).status_code
        for numero in range(3, 12)
    ]
    # Nem texto que não é IP (uma quebra de linha forjaria uma linha no log) passa.
    texto = api.post(
        "/auth/entrar",
        json={"login": "fulano", "senha": "senha-errada"},
        headers={"X-Forwarded-For": "evil, nao-e-ip"},
    )

    assert tentativas == [401] * 8 + [429]
    assert texto.status_code == 429
    [(ip, _)] = eventos(banco, "login.limitado")
    assert ip == "127.0.0.1"
    [(ip, _)] = eventos(banco, "login.recusado")
    assert ip == "127.0.0.1"
    with banco.connect() as conexao:
        ips_das_sessoes = set(conexao.execute(text("SELECT ip FROM sessoes")).scalars())
    assert ips_das_sessoes == {"127.0.0.1"}

    # As escritas: a categoria criada e removida com o cabeçalho forjado, e o resto da cota.
    criada = api.post("/categorias", json={"nome": "Adubo"}, headers=dono | forjado(50))
    assert criada.status_code == 201, criada.text
    removida = api.delete(f"/categorias/{criada.json()['id']}", headers=dono | forjado(51))
    assert removida.status_code == 204, removida.text
    [(ip, _)] = eventos(banco, "categoria.removida")
    assert ip == "127.0.0.1"
    escritas = [
        api.delete("/movimentacoes/999999", headers=dono | forjado(numero % 250)).status_code
        for numero in range(119)
    ]
    assert escritas == [404] * 118 + [429]
