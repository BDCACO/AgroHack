"""Quem lançou cada movimentação (`usuario_id` e `lancado_por`)."""

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Usuario
from app.services import autenticacao
from tests.conftest import CriarUsuario

HOJE = hoje()


def cabecalho(db: Session, usuario: Usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {autenticacao.abrir_sessao(db, usuario, None)[0]}"}


@pytest.fixture
def equipe(db: Session, criar_usuario: CriarUsuario) -> dict[str, tuple[Usuario, dict]]:
    ze = criar_usuario("ze", nome="Zé do Trator")
    maria = criar_usuario("maria", papel="dono", nome="Dona Maria")
    return {"ze": (ze, cabecalho(db, ze)), "maria": (maria, cabecalho(db, maria))}


@pytest.fixture
def ureia(cliente_autenticado: TestClient, equipe: dict) -> int:
    _, dono = equipe["maria"]
    resposta = cliente_autenticado.post(
        "/api/v1/insumos", headers=dono, json={"nome": "Ureia", "unidade": "kg"}
    )
    return resposta.json()["id"]


def test_lancamento_diz_quem_lancou_na_resposta_e_na_listagem(
    cliente_autenticado: TestClient, equipe: dict, ureia: int
) -> None:
    ze, do_ze = equipe["ze"]

    resposta = cliente_autenticado.post(
        "/api/v1/movimentacoes",
        headers=do_ze,
        # usuario_id no corpo é ignorado: o autor é quem está logado, não quem ele diz ser.
        json={"insumo_id": ureia, "tipo": "entrada", "data": str(HOJE), "quantidade": 50}
        | {"usuario_id": equipe["maria"][0].id},
    )

    assert resposta.status_code == 201, resposta.text
    assert (resposta.json()["usuario_id"], resposta.json()["lancado_por"]) == (ze.id, ze.nome)
    [listada] = cliente_autenticado.get("/api/v1/movimentacoes", headers=do_ze).json()
    assert (listada["usuario_id"], listada["lancado_por"]) == (ze.id, "Zé do Trator")
    detalhe = cliente_autenticado.get(f"/api/v1/insumos/{ureia}", headers=do_ze).json()
    assert detalhe["movimentacoes"][0]["lancado_por"] == "Zé do Trator"


def test_fila_do_app_e_contagem_dizem_quem_lancou(
    cliente_autenticado: TestClient, equipe: dict, ureia: int
) -> None:
    ze, do_ze = equipe["ze"]
    fila = [
        {"uuid": str(uuid4()), "insumo_id": ureia, "tipo": "entrada", "data": str(HOJE)}
        | {"quantidade": 10},
        {"uuid": str(uuid4()), "insumo_id": ureia, "tipo": "saida", "data": str(HOJE)}
        | {"quantidade": 2},
    ]

    lote = cliente_autenticado.post(
        "/api/v1/movimentacoes/lote", headers=do_ze, json={"movimentacoes": fila}
    ).json()
    contagem = cliente_autenticado.post(
        f"/api/v1/insumos/{ureia}/inventario", headers=do_ze, json={"quantidade_contada": 7}
    ).json()

    assert [r["movimentacao"]["lancado_por"] for r in lote["resultados"]] == [ze.nome] * 2
    assert contagem["movimentacao"]["usuario_id"] == ze.id


def test_reenvio_por_outro_usuario_mantem_quem_lancou_primeiro(
    cliente_autenticado: TestClient, equipe: dict, ureia: int
) -> None:
    ze, do_ze = equipe["ze"]
    _, dono = equipe["maria"]
    lancamento = {"uuid": str(uuid4()), "insumo_id": ureia, "tipo": "entrada"} | {
        "data": str(HOJE),
        "quantidade": 3,
    }
    cliente_autenticado.post("/api/v1/movimentacoes", headers=do_ze, json=lancamento)

    reenvio = cliente_autenticado.post("/api/v1/movimentacoes", headers=dono, json=lancamento)

    assert reenvio.status_code == 200
    assert reenvio.json()["usuario_id"] == ze.id


def test_importacao_diz_quem_importou(
    cliente_autenticado: TestClient, equipe: dict, ureia: int
) -> None:
    maria, dono = equipe["maria"]
    planilha = (
        "data;insumo;unidade;tipo;quantidade\n"
        f"{HOJE - timedelta(days=2):%d/%m/%Y};Ureia;kg;entrada;100\n"
        f"{HOJE - timedelta(days=1):%d/%m/%Y};Calcário;t;entrada;5\n"
    )

    resposta = cliente_autenticado.post(
        "/api/v1/importacoes", headers=dono, json={"conteudo": planilha, "confirmar": True}
    )

    assert resposta.json()["importado"] is True
    movimentacoes = cliente_autenticado.get("/api/v1/movimentacoes", headers=dono).json()
    assert {(m["usuario_id"], m["lancado_por"]) for m in movimentacoes} == {
        (maria.id, "Dona Maria")
    }


def test_desligada_e_sem_login_ninguem_e_o_autor(client: TestClient) -> None:
    insumo = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"}).json()

    resposta = client.post(
        "/api/v1/movimentacoes",
        json={"insumo_id": insumo["id"], "tipo": "entrada", "data": str(HOJE), "quantidade": 1},
    )

    assert (resposta.json()["usuario_id"], resposta.json()["lancado_por"]) == (None, None)
