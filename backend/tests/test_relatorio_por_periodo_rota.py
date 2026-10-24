"""GET /relatorios/periodo: as somas do domínio (tests/test_relatorio_por_periodo.py) a
partir do banco, com os filtros, o padrão de doze meses e os erros de uso."""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.relogio import hoje

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def post(client: TestClient, rota: str, **corpo: Any) -> dict[str, Any]:
    resposta = client.post(f"/api/v1/{rota}", json=corpo)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()


@pytest.fixture
def safra(client: TestClient) -> dict[str, Any]:
    """Ureia (fertilizante) comprada de duas revendas, aplicada no talhão e em parte
    descartada; glifosato (defensivo) comprado sem preço e usado."""
    adubo = post(client, "categorias", nome="Fertilizante")
    defensivo = post(client, "categorias", nome="Defensivo agrícola")
    ureia = post(client, "insumos", nome="Ureia", unidade="kg", categoria_id=adubo["id"])
    glifo = post(client, "insumos", nome="Glifosato", unidade="L", categoria_id=defensivo["id"])
    norte = post(client, "talhoes", nome="Norte", area_ha=10)
    agro = post(client, "fornecedores", nome="Agro Norte")
    casa = post(client, "fornecedores", nome="Casa do Adubo")
    u, g = ureia["id"], glifo["id"]

    for corpo in (
        {"insumo_id": u, "tipo": "entrada", "data": dia(20), "quantidade": 1000,
         "valor_unitario": 3.1, "fornecedor_id": agro["id"]},
        {"insumo_id": u, "tipo": "entrada", "data": dia(20), "quantidade": 500,
         "valor_unitario": 2.9, "fornecedor_id": casa["id"]},
        {"insumo_id": g, "tipo": "entrada", "data": dia(19), "quantidade": 40,
         "fornecedor_id": agro["id"]},
        {"insumo_id": u, "tipo": "saida", "data": dia(10), "quantidade": 200,
         "talhao_id": norte["id"]},
        {"insumo_id": u, "tipo": "saida", "data": dia(9), "quantidade": 100},
        {"insumo_id": g, "tipo": "saida", "data": dia(9), "quantidade": 5},
        {"insumo_id": u, "tipo": "saida", "data": dia(5), "quantidade": 50, "motivo": "descarte"},
    ):  # fmt: skip
        post(client, "movimentacoes", **corpo)
    # Saldo de 1150 kg, contados 1140: 10 kg de falta.
    contagem = client.post(
        f"/api/v1/insumos/{u}/inventario", json={"quantidade_contada": 1140, "data": dia(3)}
    )
    assert contagem.json()["diferenca"] == -10
    return {
        "adubo": adubo,
        "defensivo": defensivo,
        "ureia": ureia,
        "glifo": glifo,
        "norte": norte,
        "agro": agro,
        "casa": casa,
    }


def relatorio(client: TestClient, consulta: str) -> dict[str, Any]:
    resposta = client.get(f"/api/v1/relatorios/periodo{consulta}")
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def test_relatorio_por_dia_com_os_totais(client: TestClient, safra: dict[str, Any]) -> None:
    r = relatorio(client, f"?desde={dia(20)}&ate={dia(0)}&agrupar=dia")

    assert len(r["periodos"]) == 21  # todo dia, com ou sem movimento
    vazio = next(p for p in r["periodos"] if p["inicio"] == dia(15))
    assert (vazio["gasto"], vazio["perdas"], vazio["consumo"]) == (0, 0, [])
    total = r["total"]
    # Custo médio da ureia: (1000 × 3,10 + 500 × 2,90) / 1500 = R$ 3,03.
    consumo = [(c["insumo"], c["unidade"], c["quantidade"], c["valor"]) for c in total["consumo"]]
    assert consumo == [("Glifosato", "L", 5, None), ("Ureia", "kg", 300, 909.0)]
    assert (total["gasto"], total["compras_sem_preco"]) == (4550.0, 1)
    assert total["perdas"] == 181.8  # (50 descartados + 10 de falta) × R$ 3,03
    categorias = [
        (c["categoria"], c["gasto"], c["consumo"], c["perdas"]) for c in total["por_categoria"]
    ]
    assert categorias == [
        ("Defensivo agrícola", 0, 0, 0),
        ("Fertilizante", 4550.0, 909.0, 181.8),
    ]
    fornecedores = [(f["fornecedor"], f["gasto"], f["compras"]) for f in total["por_fornecedor"]]
    assert fornecedores == [("Agro Norte", 3100.0, 2), ("Casa do Adubo", 1450.0, 1)]
    assert "1 compra sem preço ficou fora do gasto." in r["limitacoes"]
    # Os períodos somam o total.
    assert sum(p["gasto"] for p in r["periodos"]) == total["gasto"]
    assert round(sum(p["perdas"] for p in r["periodos"]), 2) == total["perdas"]


def test_perdas_batem_com_o_resumo(client: TestClient, safra: dict[str, Any]) -> None:
    r = relatorio(client, f"?desde={dia(30)}&ate={dia(0)}")
    assert r["total"]["perdas"] == client.get("/api/v1/resumo").json()["perdas"]["total"]


def test_padrao_sao_os_ultimos_doze_meses_por_mes(client: TestClient) -> None:
    r = relatorio(client, "")

    # Do primeiro dia do mês, onze meses atrás, até hoje: doze meses com o atual.
    meses = HOJE.year * 12 + HOJE.month - 1 - 11
    assert (r["agrupar"], r["ate"]) == ("mes", str(HOJE))
    assert r["desde"] == str(date(meses // 12, meses % 12 + 1, 1))
    assert len(r["periodos"]) == 12
    assert r["periodos"][-1]["fim"] == str(HOJE)
    # Sem nada lançado: tudo zero, e nenhuma limitação a dizer.
    assert r["total"]["gasto"] == r["total"]["perdas"] == 0
    assert r["limitacoes"] == []


def test_filtros_do_relatorio(client: TestClient, safra: dict[str, Any]) -> None:
    periodo = f"?desde={dia(30)}&ate={dia(0)}"

    defensivo = relatorio(client, f"{periodo}&categoria_id={safra['defensivo']['id']}")
    assert [c["insumo"] for c in defensivo["total"]["consumo"]] == ["Glifosato"]
    ureia = relatorio(client, f"{periodo}&insumo_id={safra['ureia']['id']}")
    assert (ureia["total"]["gasto"], ureia["total"]["compras_sem_preco"]) == (4550.0, 0)
    # No talhão, só as aplicações: compra e perda não são de talhão, e o relatório diz.
    norte = relatorio(client, f"{periodo}&talhao_id={safra['norte']['id']}")
    assert [c["quantidade"] for c in norte["total"]["consumo"]] == [200]
    assert (norte["total"]["gasto"], norte["total"]["perdas"]) == (0, 0)
    assert any("talhão" in limitacao for limitacao in norte["limitacoes"])
    casa = relatorio(client, f"{periodo}&fornecedor_id={safra['casa']['id']}")
    assert (casa["total"]["gasto"], casa["total"]["consumo"]) == (1450.0, [])
    assert any("fornecedor" in limitacao for limitacao in casa["limitacoes"])


@pytest.mark.parametrize(
    ("consulta", "frase"),
    [
        ("?desde=2026-05-10&ate=2026-05-01", "troque as datas"),
        ("?desde=2025-01-01&ate=2026-02-05&agrupar=dia", "401 dias"),
        ("?agrupar=ano", None),
        ("?desde=ontem", None),
    ],
)
def test_pedido_invalido_e_422(client: TestClient, consulta: str, frase: str | None) -> None:
    resposta = client.get(f"/api/v1/relatorios/periodo{consulta}")
    assert resposta.status_code == 422
    if frase:
        assert frase in resposta.json()["detail"]


def test_poucas_consultas_ao_banco(client: TestClient, safra: dict[str, Any], db: Session) -> None:
    # Sem uma ida ao banco por insumo ou por período (N+1): as consultas não crescem com
    # os dados nem com os 31 dias pedidos.
    consultas: list[str] = []

    def contar(*argumentos: Any) -> None:
        consultas.append(argumentos[2])

    event.listen(db.get_bind(), "before_cursor_execute", contar)
    try:
        relatorio(client, f"?desde={dia(30)}&ate={dia(0)}&agrupar=dia")
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", contar)

    assert len(consultas) <= 3, consultas
