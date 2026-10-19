"""Cadastro de insumos e movimentações pela API, com o banco de teste (SQLite)."""

from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.relogio import hoje

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def criar(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/insumos", json={"nome": "Ureia", "unidade": "kg"} | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def lancar(client: TestClient, **campos: Any) -> dict[str, Any]:
    resposta = client.post("/api/v1/movimentacoes", json=campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


def test_cadastro_de_insumo_e_nome_duplicado(client: TestClient) -> None:
    insumo = criar(client, estoque_minimo=10)

    assert insumo["estoque_atual"] == 0
    assert [(a["tipo"], a["gravidade"]) for a in insumo["analise"]["alertas"]] == [
        ("abaixo_do_minimo", "alta")
    ]
    # Espaços nas pontas não fazem um nome novo.
    duplicado = client.post("/api/v1/insumos", json={"nome": " Ureia ", "unidade": "kg"})
    assert duplicado.status_code == 409


def test_estoque_e_analise_saem_das_movimentacoes(client: TestClient) -> None:
    insumo = criar(client, estoque_minimo=10, prazo_reposicao_dias=15)
    validade = str(HOJE + timedelta(days=10))
    lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(30),
        quantidade=100,
        validade=validade,
    )
    for dias_atras in range(30):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=2)

    [listado] = client.get("/api/v1/insumos").json()

    # 100 entraram, 30 × 2 saíram; o lote é o mesmo, então sobram 40 kg dele.
    assert listado["estoque_atual"] == 40
    assert listado["analise"]["consumo_diario"] == pytest.approx(60 / 31)
    vencimento = [a for a in listado["analise"]["alertas"] if a["tipo"] == "vencimento_proximo"]
    assert vencimento[0]["justificativa"].startswith("40 kg vencem em")
    assert any("Saldo por lote estimado" in t for t in listado["analise"]["limitacoes"])


@pytest.mark.parametrize(
    "mudanca",
    [
        {"tipo": "saida", "validade": dia(-30)},  # validade só em entrada
        {"data": dia(-1)},  # data futura
        {"quantidade": 0},
        {"insumo_id": 999},
    ],
)
def test_movimentacao_invalida_e_recusada(client: TestClient, mudanca: dict[str, Any]) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "entrada", "data": dia(0), "quantidade": 5}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | mudanca)

    assert resposta.status_code == 422


def test_atualizar_insumo(client: TestClient) -> None:
    ureia = criar(client)
    criar(client, nome="Calcário", unidade="t")

    atualizado = client.put(
        f"/api/v1/insumos/{ureia['id']}",
        json={"nome": "Ureia 45%", "unidade": "kg", "estoque_minimo": 50},
    )
    assert atualizado.status_code == 200
    assert (atualizado.json()["nome"], atualizado.json()["estoque_minimo"]) == ("Ureia 45%", 50)

    duplicado = {"nome": "Calcário", "unidade": "t"}
    assert client.put(f"/api/v1/insumos/{ureia['id']}", json=duplicado).status_code == 409
    assert client.put("/api/v1/insumos/999", json=duplicado).status_code == 404


def test_listar_e_remover_movimentacoes(client: TestClient) -> None:
    ureia, calcario = criar(client), criar(client, nome="Calcário", unidade="t")
    antiga = lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(5), quantidade=10)
    recente = lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(1), quantidade=3)
    lancar(client, insumo_id=calcario["id"], tipo="entrada", data=dia(2), quantidade=4)

    da_ureia = client.get("/api/v1/movimentacoes", params={"insumo_id": ureia["id"]}).json()
    assert [m["id"] for m in da_ureia] == [recente["id"], antiga["id"]]
    assert len(client.get("/api/v1/movimentacoes", params={"limite": 2}).json()) == 2

    assert client.delete(f"/api/v1/movimentacoes/{recente['id']}").status_code == 204
    assert client.delete(f"/api/v1/movimentacoes/{recente['id']}").status_code == 404
    estoques = {i["nome"]: i["estoque_atual"] for i in client.get("/api/v1/insumos").json()}
    assert estoques == {"Calcário": 4, "Ureia": 10}
