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
        {"motivo": "descarte"},  # descarte é saída
        {"tipo": "saida", "motivo": "perdi"},
    ],
)
def test_movimentacao_invalida_e_recusada(client: TestClient, mudanca: dict[str, Any]) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "entrada", "data": dia(0), "quantidade": 5}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | mudanca)

    assert resposta.status_code == 422


def test_descarte_tira_o_lote_vencido_sem_contar_como_consumo(client: TestClient) -> None:
    insumo = criar(client)
    vencido = dia(10)
    lancar(
        client,
        insumo_id=insumo["id"],
        tipo="entrada",
        data=dia(60),
        quantidade=10,
        validade=vencido,
    )
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(60), quantidade=20)
    # Retiradas só depois do vencimento: saem do lote bom, e o vencido fica inteiro.
    for dias_atras in range(0, 10, 2):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=1)
    antes = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert "vencido" in [a["tipo"] for a in antes["analise"]["alertas"]]

    descarte = lancar(
        client, insumo_id=insumo["id"], tipo="saida", motivo="descarte", data=dia(0), quantidade=10
    )

    depois = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert descarte["motivo"] == "descarte"
    assert depois["estoque_atual"] == antes["estoque_atual"] - 10
    assert "vencido" not in [a["tipo"] for a in depois["analise"]["alertas"]]
    # O consumo é o das 5 retiradas: os 10 descartados não entram na conta.
    assert depois["analise"]["consumo_diario"] == antes["analise"]["consumo_diario"]
    assert depois["movimentacoes"][0]["motivo"] == "descarte"


def contar(client: TestClient, insumo_id: int, **corpo: Any) -> dict[str, Any]:
    resposta = client.post(f"/api/v1/insumos/{insumo_id}/inventario", json=corpo)
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def test_inventario_com_falta_lanca_a_diferenca_sem_virar_consumo(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(40), quantidade=100)
    for dias_atras in range(0, 40, 4):
        lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(dias_atras), quantidade=2)
    antes = client.get(f"/api/v1/insumos/{insumo['id']}").json()

    ajuste = contar(client, insumo["id"], quantidade_contada=70)

    assert (ajuste["saldo_registrado"], ajuste["quantidade_contada"]) == (80, 70)
    assert ajuste["diferenca"] == -10
    assert ajuste["movimentacao"] | {"id": 0} == {
        "id": 0,
        "insumo_id": insumo["id"],
        "tipo": "saida",
        "motivo": "inventario",
        "data": dia(0),
        "quantidade": 10,
        "validade": None,
    }
    depois = client.get(f"/api/v1/insumos/{insumo['id']}").json()
    assert depois["estoque_atual"] == 70
    assert depois["analise"]["consumo_diario"] == antes["analise"]["consumo_diario"]
    assert any("inventário" in t for t in depois["analise"]["limitacoes"])


def test_inventario_com_sobra_lanca_uma_entrada(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(10), quantidade=5)

    ajuste = contar(client, insumo["id"], quantidade_contada=7.5, data=dia(2))

    assert ajuste["diferenca"] == 2.5
    assert ajuste["movimentacao"]["tipo"] == "entrada"
    assert ajuste["movimentacao"]["data"] == dia(2)
    assert client.get("/api/v1/insumos").json()[0]["estoque_atual"] == 7.5


def test_inventario_compara_com_o_saldo_da_data_da_contagem(client: TestClient) -> None:
    insumo = criar(client)
    lancar(client, insumo_id=insumo["id"], tipo="entrada", data=dia(10), quantidade=50)
    lancar(client, insumo_id=insumo["id"], tipo="saida", data=dia(1), quantidade=20)

    # Contou 50 há 5 dias: batia com o registro daquele dia; a saída de depois não conta.
    ajuste = contar(client, insumo["id"], quantidade_contada=50, data=dia(5))

    assert (ajuste["diferenca"], ajuste["movimentacao"]) == (0, None)
    assert len(client.get("/api/v1/movimentacoes").json()) == 2


@pytest.mark.parametrize(
    "corpo", [{"quantidade_contada": -1}, {"quantidade_contada": 5, "data": dia(-1)}, {}]
)
def test_inventario_invalido(client: TestClient, corpo: dict[str, Any]) -> None:
    insumo = criar(client)

    resposta = client.post(f"/api/v1/insumos/{insumo['id']}/inventario", json=corpo)

    assert resposta.status_code == 422
    inexistente = client.post("/api/v1/insumos/999/inventario", json={"quantidade_contada": 1})
    assert inexistente.status_code == 404


def test_movimentacao_de_inventario_so_pela_contagem(client: TestClient) -> None:
    insumo = criar(client)
    corpo = {"insumo_id": insumo["id"], "tipo": "saida", "data": dia(0), "quantidade": 1}

    resposta = client.post("/api/v1/movimentacoes", json=corpo | {"motivo": "inventario"})

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


def test_detalhe_traz_o_historico_do_estoque(client: TestClient) -> None:
    ureia = criar(client)
    lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(10), quantidade=100)
    lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(10), quantidade=20)
    lancar(client, insumo_id=ureia["id"], tipo="saida", data=dia(3), quantidade=30)

    detalhe = client.get(f"/api/v1/insumos/{ureia['id']}").json()

    assert detalhe["estoque_atual"] == 50
    # Um ponto por dia com movimentação: o saldo no fim daquele dia.
    assert detalhe["historico"] == [
        {"data": dia(10), "saldo": 80},
        {"data": dia(3), "saldo": 50},
    ]
    assert [m["quantidade"] for m in detalhe["movimentacoes"]] == [30, 20, 100]
    assert client.get("/api/v1/insumos/999").status_code == 404


def test_remover_insumo_leva_as_movimentacoes(client: TestClient) -> None:
    ureia = criar(client)
    lancar(client, insumo_id=ureia["id"], tipo="entrada", data=dia(1), quantidade=10)

    assert client.delete(f"/api/v1/insumos/{ureia['id']}").status_code == 204

    assert client.get("/api/v1/insumos").json() == []
    assert client.get("/api/v1/movimentacoes").json() == []
    assert client.delete(f"/api/v1/insumos/{ureia['id']}").status_code == 404
