"""Os cabeçalhos de segurança em toda resposta da API, inclusive nos erros e no download
do Excel, e a CSP própria do Swagger, que ele precisa para abrir."""

import base64
import hashlib
import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

FIXOS = {
    # O navegador não adivinha o tipo: um JSON nunca vira HTML ou script.
    "X-Content-Type-Options": "nosniff",
    # Nenhuma resposta da API vai para dentro de um <iframe> de outro site.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    # Outro site não embute a resposta (<img>, <script>) com o login de quem o visita.
    "Cross-Origin-Resource-Policy": "same-origin",
    # Dado da fazenda (preços, estoque, quem entrou) não fica no cache do navegador nem de
    # um proxy no caminho.
    "Cache-Control": "no-store",
}
CSP_DA_API = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def conferir_os_fixos(cabecalhos: dict[str, str] | object) -> None:
    for nome, valor in FIXOS.items():
        assert cabecalhos[nome] == valor, nome  # type: ignore[index]


@pytest.mark.parametrize(
    ("metodo", "caminho", "status"),
    [
        ("GET", "/api/v1/health", 200),
        ("GET", "/api/v1/insumos", 200),
        ("GET", "/api/v1/insumos/999", 404),
        ("POST", "/api/v1/insumos", 422),
        ("GET", "/api/v1/openapi.json", 200),
        ("GET", "/nao-existe", 404),
        ("DELETE", "/api/v1/health", 405),
    ],
)
def test_toda_resposta_leva_os_cabecalhos(
    client: TestClient, metodo: str, caminho: str, status: int
) -> None:
    resposta = client.request(metodo, caminho)

    assert resposta.status_code == status
    conferir_os_fixos(resposta.headers)
    assert resposta.headers["Content-Security-Policy"] == CSP_DA_API
    assert "Strict-Transport-Security" not in resposta.headers


def test_login_e_rotas_da_sessao_tambem(cliente_autenticado: TestClient) -> None:
    recusado = cliente_autenticado.post(
        "/api/v1/auth/entrar", json={"login": "ninguem", "senha": "qualquer-coisa"}
    )
    sem_login = cliente_autenticado.get("/api/v1/usuarios")

    for resposta in (recusado, sem_login):
        assert resposta.status_code == 401
        conferir_os_fixos(resposta.headers)


def test_erro_inesperado_tambem(client: TestClient) -> None:
    def quebrar() -> None:
        raise RuntimeError("defeito")

    client.app.add_api_route("/api/v1/teste-quebra", quebrar)

    resposta = client.get("/api/v1/teste-quebra")

    assert resposta.status_code == 500
    conferir_os_fixos(resposta.headers)
    assert resposta.headers["Content-Security-Policy"] == CSP_DA_API


def test_o_excel_continua_sendo_baixado(client: TestClient) -> None:
    resposta = client.get("/api/v1/relatorio.xlsx")

    assert resposta.status_code == 200
    assert resposta.headers["Content-Type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert resposta.headers["Content-Disposition"].startswith("attachment; filename=")
    assert resposta.content.startswith(b"PK")  # um .xlsx é um zip
    conferir_os_fixos(resposta.headers)


def test_o_swagger_tem_a_csp_dele_e_so_o_script_dele_roda(client: TestClient) -> None:
    # O Swagger carrega o JS e o CSS de um CDN e tem um <script> na própria página: com a
    # CSP da API ele não abriria. A dele libera o CDN e só aquele script, pelo hash.
    resposta = client.get("/api/v1/docs")

    assert resposta.status_code == 200
    conferir_os_fixos(resposta.headers)
    csp = dict(
        diretiva.strip().split(" ", 1)
        for diretiva in resposta.headers["Content-Security-Policy"].split(";")
    )
    em_linha = re.findall(r"<script>(.*?)</script>", resposta.text, re.DOTALL)
    assert em_linha
    for script in em_linha:
        hash_ = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        assert f"'sha256-{hash_}'" in csp["script-src"]
    assert "'unsafe-inline'" not in csp["script-src"]
    assert "'unsafe-eval'" not in csp["script-src"]
    for externo in re.findall(r'(?:src|href)="(https://[^/"]+)', resposta.text):
        assert externo in resposta.headers["Content-Security-Policy"]
    assert csp["default-src"] == "'none'"
    assert csp["connect-src"] == "'self'"
    assert csp["frame-ancestors"] == "'none'"


def test_hsts_so_quando_configurado() -> None:
    # Só faz sentido com HTTPS: ligado no desenvolvimento em http://, o navegador passaria
    # a recusar o http://localhost de todos os projetos por um ano.
    padrao = Settings(environment="test", database_url="sqlite://")
    assert padrao.hsts_segundos == 0

    com_https = Settings(environment="test", database_url="sqlite://", hsts_segundos=31_536_000)
    with TestClient(create_app(com_https)) as cliente:
        resposta = cliente.get("/api/v1/health")

    assert resposta.headers["Strict-Transport-Security"] == "max-age=31536000"


def test_hsts_negativo_e_recusado() -> None:
    with pytest.raises(ValueError, match="hsts_segundos"):
        Settings(environment="test", database_url="sqlite://", hsts_segundos=-1)
