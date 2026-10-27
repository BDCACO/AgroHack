"""`GET /auditoria`: os eventos, os mais recentes primeiro, com filtros e páginas. Só o
dono, e sempre com login."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session

from app.models import Usuario
from app.services import auditoria, autenticacao
from tests.conftest import CriarUsuario

AUDITORIA = "/api/v1/auditoria"


def cabecalho(db: Session, usuario: Usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {autenticacao.abrir_sessao(db, usuario, None)[0]}"}


@pytest.fixture
def equipe(db: Session, criar_usuario: CriarUsuario) -> dict[str, Usuario]:
    return {
        "maria": criar_usuario("maria", papel="dono", nome="Dona Maria"),
        "ze": criar_usuario("ze", nome="Zé do Trator"),
    }


def gravar(
    db: Session,
    quando: datetime,
    acao: str,
    entidade: str | None = None,
    entidade_id: int | None = None,
    usuario: Usuario | None = None,
) -> int:
    origem = auditoria.Origem(usuario_id=None if usuario is None else usuario.id, ip="10.0.0.5")
    evento = auditoria.registrar(db, origem, acao, entidade, entidade_id, {"x": 1})
    evento.ocorrido_em = quando
    db.commit()
    return evento.id


@pytest.fixture
def historia(db: Session, equipe: dict[str, Usuario]) -> dict[str, int]:
    """Uma semana de eventos. As horas são UTC: 03:30 UTC do dia 3 ainda é dia 2 em
    Rondônia (UTC-4)."""
    maria, ze = equipe["maria"], equipe["ze"].id

    def em(dia: int, hora: int, minuto: int = 0) -> datetime:
        return datetime(2026, 10, dia, hora, minuto, tzinfo=UTC)

    return {
        "insumo": gravar(db, em(1, 12), "insumo.removido", "insumo", 12, maria),
        "login": gravar(db, em(3, 3, 30), "login.recusado", "usuario", ze),
        "criado": gravar(db, em(4, 12), "usuario.criado", "usuario", ze, maria),
        "alterado": gravar(db, em(5, 12), "usuario.alterado", "usuario", ze, maria),
        "movimentacao": gravar(db, em(5, 12), "movimentacao.removida", "movimentacao", 40, maria),
    }


def ids(resposta: Response) -> list[int]:
    assert resposta.status_code == 200, resposta.text
    return [evento["id"] for evento in resposta.json()]


def test_dono_ve_os_eventos_mais_recentes_primeiro(
    client: TestClient, db: Session, equipe: dict, historia: dict
) -> None:
    resposta = client.get(AUDITORIA, headers=cabecalho(db, equipe["maria"]))

    # No mesmo instante, o id desempata: o gravado por último vem antes.
    assert ids(resposta) == [
        historia["movimentacao"],
        historia["alterado"],
        historia["criado"],
        historia["login"],
        historia["insumo"],
    ]
    assert resposta.headers["X-Total-Count"] == "5"
    primeiro = resposta.json()[0]
    assert primeiro == {
        "id": historia["movimentacao"],
        "ocorrido_em": primeiro["ocorrido_em"],
        "usuario_id": equipe["maria"].id,
        "feito_por": "Dona Maria",
        "acao": "movimentacao.removida",
        "entidade": "movimentacao",
        "entidade_id": 40,
        "dados": {"x": 1},
        "origem": "api",
        "ip": "10.0.0.5",
        "dispositivo": None,
    }
    assert datetime.fromisoformat(primeiro["ocorrido_em"]) == datetime(2026, 10, 5, 12, tzinfo=UTC)
    recusado = resposta.json()[3]
    assert (recusado["usuario_id"], recusado["feito_por"]) == (None, None)


@pytest.mark.parametrize(
    ("acao", "esperados"),
    [
        ("usuario.criado", ["criado"]),
        # O grupo, com ou sem o ponto.
        ("usuario.", ["alterado", "criado"]),
        ("usuario", ["alterado", "criado"]),
        ("login", ["login"]),
    ],
)
def test_filtro_por_acao_aceita_o_grupo(
    client: TestClient, db: Session, equipe: dict, historia: dict, acao: str, esperados: list
) -> None:
    resposta = client.get(AUDITORIA, params={"acao": acao}, headers=cabecalho(db, equipe["maria"]))

    assert ids(resposta) == [historia[nome] for nome in esperados]
    assert resposta.headers["X-Total-Count"] == str(len(esperados))


def test_acao_desconhecida_e_422_com_os_grupos(
    client: TestClient, db: Session, equipe: dict
) -> None:
    resposta = client.get(
        AUDITORIA, params={"acao": "usuari"}, headers=cabecalho(db, equipe["maria"])
    )

    assert resposta.status_code == 422
    assert "usuario" in resposta.json()["detail"]
    assert "movimentacao" in resposta.json()["detail"]


def test_filtros_por_usuario_entidade_e_periodo_se_somam(
    client: TestClient, db: Session, equipe: dict, historia: dict
) -> None:
    dono = cabecalho(db, equipe["maria"])
    ze = equipe["ze"].id

    def pedir(**filtros: object) -> list[int]:
        return ids(client.get(AUDITORIA, params=filtros, headers=dono))

    assert pedir(usuario_id=equipe["maria"].id) == [
        historia[n] for n in ("movimentacao", "alterado", "criado", "insumo")
    ]
    assert pedir(entidade="usuario", entidade_id=ze) == [
        historia[n] for n in ("alterado", "criado", "login")
    ]
    assert pedir(entidade="insumo") == [historia["insumo"]]
    # O dia é o de Rondônia: as 03:30 UTC do dia 3 são 23:30 do dia 2.
    assert pedir(desde="2026-10-02", ate="2026-10-02") == [historia["login"]]
    assert pedir(desde="2026-10-03", ate="2026-10-04") == [historia["criado"]]
    assert pedir(desde="2026-10-05") == [historia["movimentacao"], historia["alterado"]]
    assert pedir(ate="2026-10-01") == [historia["insumo"]]
    assert pedir(entidade="usuario", usuario_id=equipe["maria"].id, desde="2026-10-05") == [
        historia["alterado"]
    ]


def test_paginas_sem_repetir_nem_perder_evento(
    client: TestClient, db: Session, equipe: dict, historia: dict
) -> None:
    dono = cabecalho(db, equipe["maria"])
    todos = ids(client.get(AUDITORIA, headers=dono))

    paginas = [
        ids(client.get(AUDITORIA, params={"limite": 2, "deslocamento": d}, headers=dono))
        for d in (0, 2, 4)
    ]

    assert paginas == [todos[0:2], todos[2:4], todos[4:]]
    resposta = client.get(AUDITORIA, params={"limite": 2, "deslocamento": 4}, headers=dono)
    assert resposta.headers["X-Total-Count"] == "5"


@pytest.mark.parametrize(
    "filtros",
    [
        {"desde": "2026-10-05", "ate": "2026-10-01"},
        {"limite": 0},
        {"limite": 1001},
        {"deslocamento": -1},
        {"entidade": "x" * 21},
    ],
)
def test_filtros_invalidos_sao_422(
    client: TestClient, db: Session, equipe: dict, filtros: dict
) -> None:
    resposta = client.get(AUDITORIA, params=filtros, headers=cabecalho(db, equipe["maria"]))

    assert resposta.status_code == 422


def test_so_o_dono_e_sempre_com_login(
    client: TestClient, cliente_autenticado: TestClient, db: Session, equipe: dict
) -> None:
    # Desligada, sem login passa como dono em quase tudo; aqui não: a trilha diz quem tentou
    # entrar e de onde, e "quem fez" não tem sentido sem login.
    assert client.get(AUDITORIA).status_code == 401
    assert client.get(AUDITORIA, headers=cabecalho(db, equipe["ze"])).status_code == 403
    assert cliente_autenticado.get(AUDITORIA).status_code == 401
    funcionario = cliente_autenticado.get(AUDITORIA, headers=cabecalho(db, equipe["ze"]))
    assert funcionario.status_code == 403
    assert cliente_autenticado.get(AUDITORIA, headers=cabecalho(db, equipe["maria"])).json() == []
