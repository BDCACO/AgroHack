"""Talhões (/talhoes): o cadastro de onde os insumos são aplicados, as aplicações, a
carência e o custo de cada um."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.relogio import hoje

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def criar_talhao(client: TestClient, **campos: Any) -> dict[str, Any]:
    corpo = {"nome": "Talhão Norte", "area_ha": 120, "cultura": "Soja"} | campos
    resposta = client.post("/api/v1/talhoes", json=corpo)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastro_de_talhao_e_nome_duplicado(client: TestClient) -> None:
    talhao = criar_talhao(client, nome="  Talhão Norte  ", area_ha=120.5)

    cadastro = {k: talhao[k] for k in ("nome", "area_ha", "cultura", "demonstracao")}
    assert cadastro == {
        "nome": "Talhão Norte",
        "area_ha": 120.5,
        "cultura": "Soja",
        "demonstracao": False,
    }
    repetido = client.post("/api/v1/talhoes", json={"nome": "Talhão Norte", "area_ha": 3})
    assert repetido.status_code == 409
    assert repetido.json()["detail"] == "Já existe um talhão com esse nome."


def test_cultura_e_opcional(client: TestClient) -> None:
    talhao = criar_talhao(client, nome="Pasto 1", area_ha=45, cultura=None)
    sem = client.post("/api/v1/talhoes", json={"nome": "Pasto 2", "area_ha": 10})
    em_branco = criar_talhao(client, nome="Pasto 3", cultura="  ")

    assert talhao["cultura"] is None
    assert sem.json()["cultura"] is None
    assert em_branco["cultura"] is None


@pytest.mark.parametrize(
    "corpo",
    [
        {"nome": "", "area_ha": 10},
        {"nome": "Norte", "area_ha": 0},  # área é o divisor do custo por hectare
        {"nome": "Norte", "area_ha": -5},
        {"nome": "Norte", "area_ha": 100_000_000},  # passa do NUMERIC(10, 2)
        {"nome": "Nor\x0bte", "area_ha": 10},
        {"nome": "Norte", "area_ha": 10, "cultura": "So\x00ja"},
        {"nome": "N" * 121, "area_ha": 10},
        {"area_ha": 10},
    ],
)
def test_talhao_invalido_e_recusado(client: TestClient, corpo: dict[str, Any]) -> None:
    assert client.post("/api/v1/talhoes", json=corpo).status_code == 422
    assert client.get("/api/v1/talhoes").json() == []


def test_listar_alterar_detalhar_e_remover_talhao(client: TestClient) -> None:
    sul = criar_talhao(client, nome="Talhão Sul", area_ha=80, cultura="Milho")
    norte = criar_talhao(client)

    assert [t["nome"] for t in client.get("/api/v1/talhoes").json()] == [
        "Talhão Norte",
        "Talhão Sul",
    ]
    alterado = client.put(
        f"/api/v1/talhoes/{sul['id']}", json={"nome": "Talhão Sul", "area_ha": 82.25}
    )
    assert alterado.status_code == 200
    assert (alterado.json()["area_ha"], alterado.json()["cultura"]) == (82.25, None)
    duplicado = client.put(
        f"/api/v1/talhoes/{sul['id']}", json={"nome": "Talhão Norte", "area_ha": 1}
    )
    assert duplicado.status_code == 409
    assert client.get(f"/api/v1/talhoes/{norte['id']}").json()["nome"] == "Talhão Norte"

    assert client.delete(f"/api/v1/talhoes/{sul['id']}").status_code == 204
    assert client.get(f"/api/v1/talhoes/{sul['id']}").status_code == 404
    assert client.delete(f"/api/v1/talhoes/{sul['id']}").status_code == 404
    assert (
        client.put(f"/api/v1/talhoes/{sul['id']}", json={"nome": "X", "area_ha": 1}).status_code
        == 404
    )
