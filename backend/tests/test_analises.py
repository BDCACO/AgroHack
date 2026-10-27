"""POST /analises: contrato HTTP do motor. As contas ficam em test_motor_de_analise.py."""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient

REF = date(2026, 6, 30)


def pedido(**mudancas: Any) -> dict[str, Any]:
    return {
        "insumo": {
            "nome": "Ureia",
            "unidade": "kg",
            "estoque_atual": 20,
            "estoque_minimo": 10,
            "prazo_reposicao_dias": 15,
        },
        "retiradas": [{"data": str(REF - timedelta(days=i)), "quantidade": 2} for i in range(120)],
        "lotes": [{"quantidade": 5, "validade": str(REF + timedelta(days=10))}],
        "registros_desde": str(REF - timedelta(days=119)),
        "referencia": str(REF),
    } | mudancas


def test_analise_devolve_alertas_reposicao_e_limitacoes(client: TestClient) -> None:
    resposta = client.post("/api/v1/analises", json=pedido())

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["consumo_diario"] == 2
    assert [a["tipo"] for a in corpo["alertas"]] == ["risco_de_falta", "vencimento_proximo"]
    assert corpo["reposicao"]["pedir_em"] == str(REF)
    assert corpo["reposicao"]["pedir_hoje"] is True
    assert corpo["reposicao"]["justificativa"].startswith("Pedir hoje 70 kg")
    assert corpo["limitacoes"]


def test_periodo_invertido_e_recusado(client: TestClient) -> None:
    resposta = client.post(
        "/api/v1/analises", json=pedido(registros_desde=str(REF + timedelta(days=1)))
    )

    assert resposta.status_code == 422


def test_retirada_negativa_e_recusada(client: TestClient) -> None:
    resposta = client.post(
        "/api/v1/analises", json=pedido(retiradas=[{"data": str(REF), "quantidade": -1}])
    )

    assert resposta.status_code == 422


def test_custo_medio_opcional_poe_reais_nos_alertas(client: TestClient) -> None:
    corpo = pedido(lotes=[{"quantidade": 5, "validade": str(REF - timedelta(days=3))}])
    corpo["insumo"] |= {"custo_medio": 3}

    alertas = client.post("/api/v1/analises", json=corpo).json()["alertas"]

    vencido = next(a for a in alertas if a["tipo"] == "vencido")
    assert vencido["valor"] == 15
    assert vencido["justificativa"].endswith("são cerca de R$ 15,00.")
    corpo["insumo"]["custo_medio"] = 0
    assert client.post("/api/v1/analises", json=corpo).status_code == 422


def test_pedido_a_caminho_opcional_entra_na_reposicao(client: TestClient) -> None:
    a_caminho = [{"quantidade": 70, "previsto_para": str(REF + timedelta(days=5))}]

    corpo = client.post("/api/v1/analises", json=pedido(a_caminho=a_caminho)).json()

    # O que já foi pedido não se pede de novo; o alerta de falta diz quando chega.
    assert corpo["reposicao"]["pedir_hoje"] is False
    risco = next(a for a in corpo["alertas"] if a["tipo"] == "risco_de_falta")
    assert risco["gravidade"] == "media"
    assert "Já foram pedidos 70 kg." in risco["justificativa"]
    sem_data = client.post("/api/v1/analises", json=pedido(a_caminho=[{"quantidade": 70}]))
    assert sem_data.status_code == 200
    negativo = pedido(a_caminho=[{"quantidade": -1}])
    assert client.post("/api/v1/analises", json=negativo).status_code == 422
