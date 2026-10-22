"""A matriz de permissões: cada rota do app num nível, e cada nível cumprido de verdade.

A tabela abaixo é a mesma de docs/ARQUITETURA.md. Rota nova que não entrar nela derruba
`test_toda_rota_do_app_esta_na_matriz`: nenhuma nasce aberta por esquecimento.
"""

import re

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import permissoes
from app.main import create_app
from app.models import Usuario
from app.services import autenticacao
from tests.conftest import CriarUsuario

# Sem login, sempre.
PUBLICA = "pública"
# Qualquer usuário logado, sobre a própria sessão; exige login mesmo com a autenticação
# desligada (sem login, não há de quem falar).
SESSAO = "sessão"
# O funcionário, o peão que lança no campo: lê e lança. O dono também pode.
FUNCIONARIO = "funcionário"
# Só o dono: cadastro, remoção, planilhas, relatório, análise avulsa.
DONO = "dono"
# Gestão de usuários: só o dono, e sempre com login, mesmo com a autenticação desligada.
# Sem isso, desligada, qualquer um na rede criaria um dono para si.
GESTAO = "dono, sempre com login"

MATRIZ = {
    ("GET", "/api/v1/health"): PUBLICA,
    ("GET", "/api/v1/ready"): PUBLICA,
    ("GET", "/api/v1/docs"): PUBLICA,
    ("GET", "/docs/oauth2-redirect"): PUBLICA,  # o FastAPI a põe fora do prefixo
    ("GET", "/api/v1/openapi.json"): PUBLICA,
    ("POST", "/api/v1/auth/entrar"): PUBLICA,
    ("POST", "/api/v1/auth/sair"): SESSAO,
    ("GET", "/api/v1/auth/eu"): SESSAO,
    ("PUT", "/api/v1/auth/senha"): SESSAO,
    ("GET", "/api/v1/insumos"): FUNCIONARIO,
    ("GET", "/api/v1/insumos/{insumo_id}"): FUNCIONARIO,
    ("GET", "/api/v1/resumo"): FUNCIONARIO,
    ("GET", "/api/v1/movimentacoes"): FUNCIONARIO,
    ("POST", "/api/v1/movimentacoes"): FUNCIONARIO,
    ("POST", "/api/v1/movimentacoes/lote"): FUNCIONARIO,
    ("POST", "/api/v1/insumos/{insumo_id}/inventario"): FUNCIONARIO,
    ("GET", "/api/v1/talhoes"): FUNCIONARIO,
    ("GET", "/api/v1/talhoes/{talhao_id}"): FUNCIONARIO,
    ("POST", "/api/v1/insumos"): DONO,
    ("PUT", "/api/v1/insumos/{insumo_id}"): DONO,
    ("DELETE", "/api/v1/insumos/{insumo_id}"): DONO,
    ("DELETE", "/api/v1/movimentacoes/{movimentacao_id}"): DONO,
    ("POST", "/api/v1/importacoes"): DONO,
    ("GET", "/api/v1/importacoes/modelo.xlsx"): DONO,
    ("GET", "/api/v1/relatorio.xlsx"): DONO,
    ("POST", "/api/v1/talhoes"): DONO,
    ("PUT", "/api/v1/talhoes/{talhao_id}"): DONO,
    ("DELETE", "/api/v1/talhoes/{talhao_id}"): DONO,
    ("POST", "/api/v1/analises"): DONO,
    ("GET", "/api/v1/usuarios"): GESTAO,
    ("POST", "/api/v1/usuarios"): GESTAO,
    ("PUT", "/api/v1/usuarios/{usuario_id}"): GESTAO,
    ("PUT", "/api/v1/usuarios/{usuario_id}/senha"): GESTAO,
}

# A dependência que marca cada nível (aplicada no include_router, em app/api/router.py).
_DEPENDENCIA_DO_NIVEL = {
    permissoes.exigir_sessao: SESSAO,
    permissoes.exigir_funcionario: FUNCIONARIO,
    permissoes.exigir_dono: DONO,
    permissoes.exigir_dono_com_login: GESTAO,
}


def _rotas_do_app() -> dict[tuple[str, str], str]:
    """Cada (método, caminho) do app com o nível que as dependências dele declaram."""
    declaradas = {}
    # O FastAPI guarda os routers incluídos sem achatar: `iter_route_contexts` é como o
    # próprio gerador do OpenAPI enxerga cada rota, com as dependências do include_router.
    for rota in iter_route_contexts(create_app().routes):
        dependencias = getattr(rota, "dependencies", [])
        niveis = {_DEPENDENCIA_DO_NIVEL.get(d.dependency) for d in dependencias} - {None}
        assert len(niveis) <= 1, f"{rota.path} está em mais de um nível: {niveis}"
        for metodo in rota.methods - {"HEAD"}:
            declaradas[(metodo, rota.path)] = next(iter(niveis), PUBLICA)
    return declaradas


def test_toda_rota_do_app_esta_na_matriz() -> None:
    assert _rotas_do_app() == MATRIZ


def _url(caminho: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", caminho)


def _pedir(cliente: TestClient, metodo: str, caminho: str, token: str | None = None) -> int:
    cabecalho = {} if token is None else {"Authorization": f"Bearer {token}"}
    corpo = None if metodo in {"GET", "DELETE"} else {}
    return cliente.request(metodo, _url(caminho), headers=cabecalho, json=corpo).status_code


def _token(db: Session, usuario: Usuario) -> str:
    # Sem passar pelo login: o scrypt de cada um somaria segundos à matriz inteira.
    return autenticacao.abrir_sessao(db, usuario, None)[0]


_DA_API = [chave for chave in MATRIZ if "/docs" not in chave[1] and "openapi" not in chave[1]]


@pytest.mark.parametrize(("metodo", "caminho"), _DA_API)
def test_ligada_a_matriz_vale_para_cada_papel(
    cliente_autenticado: TestClient,
    criar_usuario: CriarUsuario,
    db: Session,
    metodo: str,
    caminho: str,
) -> None:
    nivel = MATRIZ[(metodo, caminho)]
    funcionario = _token(db, criar_usuario("ze"))
    dono = _token(db, criar_usuario("maria", papel="dono"))

    sem_token = _pedir(cliente_autenticado, metodo, caminho)
    assert (sem_token == 401) == (nivel != PUBLICA), sem_token
    com_token_falso = _pedir(cliente_autenticado, metodo, caminho, "token-inventado")
    assert (com_token_falso == 401) == (nivel != PUBLICA), com_token_falso
    do_funcionario = _pedir(cliente_autenticado, metodo, caminho, funcionario)
    assert (do_funcionario == 403) == (nivel in {DONO, GESTAO}), do_funcionario
    assert do_funcionario != 401
    assert _pedir(cliente_autenticado, metodo, caminho, dono) not in {401, 403}


@pytest.mark.parametrize(("metodo", "caminho"), _DA_API)
def test_desligada_sem_token_passa_mas_o_papel_do_token_vale(
    client: TestClient, criar_usuario: CriarUsuario, db: Session, metodo: str, caminho: str
) -> None:
    nivel = MATRIZ[(metodo, caminho)]
    funcionario = _token(db, criar_usuario("ze"))

    sem_token = _pedir(client, metodo, caminho)
    assert (sem_token == 401) == (nivel in {SESSAO, GESTAO}), sem_token
    assert (_pedir(client, metodo, caminho, "token-inventado") == 401) == (nivel != PUBLICA)
    assert (_pedir(client, metodo, caminho, funcionario) == 403) == (nivel in {DONO, GESTAO})
