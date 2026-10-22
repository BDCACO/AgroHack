"""GET /resumo: a visão geral em reais para o Painel e o app."""

from collections import Counter
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.relogio import hoje

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def criar(client: TestClient, nome: str, **campos: Any) -> int:
    resposta = client.post("/api/v1/insumos", json={"nome": nome, "unidade": "kg"} | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


def lancar(
    client: TestClient, insumo_id: int, tipo: str, dias_atras: int, quantidade: float, **campos: Any
) -> None:
    corpo = {
        "insumo_id": insumo_id,
        "tipo": tipo,
        "data": dia(dias_atras),
        "quantidade": quantidade,
    } | campos
    resposta = client.post("/api/v1/movimentacoes", json=corpo)
    assert resposta.status_code == 201, resposta.json()


def test_resumo_sem_nada_cadastrado(client: TestClient) -> None:
    assert client.get("/api/v1/resumo").json() == {
        "insumos": 0,
        "valor_em_estoque": None,
        "insumos_sem_preco": 0,
        "perdas": {"ultimos_30_dias": 0, "total": 0},
        "compras_sugeridas": {"valor": None, "pedidos": 0, "pedir_hoje": 0},
        "alertas": {"alta": 0, "media": 0, "baixa": 0},
        "talhoes_em_carencia": 0,
        "limitacoes": [],
    }


def test_resumo_conta_os_talhoes_em_carencia_a_parte_dos_alertas(client: TestClient) -> None:
    fungicida = criar(client, "Fungicida", carencia_dias=30)
    lancar(client, fungicida, "entrada", 60, 10)
    norte, sul, _ = (
        client.post("/api/v1/talhoes", json={"nome": nome, "area_ha": 10}).json()["id"]
        for nome in ("Norte", "Sul", "Leste")
    )
    lancar(client, fungicida, "saida", 5, 1, talhao_id=norte)  # em carência
    lancar(client, fungicida, "saida", 40, 1, talhao_id=sul)  # já liberado

    resumo = client.get("/api/v1/resumo").json()

    assert resumo["talhoes_em_carencia"] == 1
    # Os alertas por gravidade continuam sendo os dos insumos: a carência é do talhão, e o
    # Painel mostra a lista dos insumos ao lado desses números.
    insumo = client.get(f"/api/v1/insumos/{fungicida}").json()
    assert sum(resumo["alertas"].values()) == len(insumo["analise"]["alertas"])


def test_resumo_soma_estoque_perdas_e_compras_em_reais(client: TestClient) -> None:
    ureia = criar(client, "Ureia", estoque_minimo=10, prazo_reposicao_dias=15)
    # (50 × 3 + 100 × 2,5 + 100 × 3,5) / 250 = R$ 3,00/kg
    lancar(client, ureia, "entrada", 50, 50, valor_unitario=3)
    lancar(client, ureia, "entrada", 30, 100, valor_unitario=2.5)
    lancar(client, ureia, "entrada", 20, 100, valor_unitario=3.5)
    for dias_atras in range(30):
        lancar(client, ureia, "saida", dias_atras, 2)
    lancar(client, ureia, "saida", 45, 10, motivo="descarte")  # fora dos 30 dias: R$ 30
    lancar(client, ureia, "saida", 5, 4, motivo="descarte")  # R$ 12
    contagem = client.post(f"/api/v1/insumos/{ureia}/inventario", json={"quantidade_contada": 174})
    assert contagem.json()["diferenca"] == -2  # falta de 2 kg: R$ 6

    # Acaba antes da entrega: pedir hoje, com custo estimado.
    sal = criar(client, "Sal", estoque_minimo=5, prazo_reposicao_dias=7)
    lancar(client, sal, "entrada", 30, 100, valor_unitario=2)
    for dias_atras in range(30):
        lancar(client, sal, "saida", dias_atras, 3)

    # Sem preço: a perda dele não tem como virar reais.
    vacina = criar(client, "Vacina")
    lancar(client, vacina, "entrada", 20, 50)
    lancar(client, vacina, "saida", 3, 5, motivo="descarte")

    resumo = client.get("/api/v1/resumo").json()
    insumos = {i["nome"]: i for i in client.get("/api/v1/insumos").json()}

    assert resumo["insumos"] == 3
    # 174 kg × 3,00 + 10 kg × 2,00
    assert resumo["valor_em_estoque"] == pytest.approx(542)
    assert resumo["insumos_sem_preco"] == 1
    assert resumo["perdas"] == {"ultimos_30_dias": 18, "total": 48}
    reposicao_do_sal = insumos["Sal"]["analise"]["reposicao"]
    assert reposicao_do_sal["pedir_hoje"] is True
    assert resumo["compras_sugeridas"] == {
        "valor": pytest.approx(reposicao_do_sal["custo_estimado"]),
        "pedidos": 1,
        "pedir_hoje": 1,
    }
    gravidades = Counter(a["gravidade"] for i in insumos.values() for a in i["analise"]["alertas"])
    assert resumo["alertas"] == {g: gravidades[g] for g in ("alta", "media", "baixa")}
    assert resumo["limitacoes"] == [
        "1 insumo sem preço nas compras fica fora do valor em estoque, das perdas e do custo "
        "das compras.",
        "Perdas valorizadas pelo custo médio de hoje, não pelo preço da época.",
    ]
