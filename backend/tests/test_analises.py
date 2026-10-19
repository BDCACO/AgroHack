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
