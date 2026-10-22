"""Números mais precisos que a coluna, no PostgreSQL de verdade. O SQLite guarda o float
como veio e não arredonda: estes casos só aparecem aqui. Vieram da revisão de código."""

import uuid
from datetime import timedelta
from typing import Any

import httpx

from app.core.relogio import hoje

HOJE = str(hoje())


def insumo(api: httpx.Client, **campos: Any) -> int:
    resposta = api.post("/insumos", json={"nome": "Ureia", "unidade": "kg"} | campos)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def test_reenvio_identico_com_meio_de_casa_continua_sendo_o_mesmo(api: httpx.Client) -> None:
    # 1,2345 vira 1,235 no banco; o round() do Python daria 1,234. R$ 12,35 o quilo em
    # gramas (0,01235) vira 0,0124. O reenvio do app tem de bater com o gravado.
    corpo = {
        "uuid": str(uuid.uuid4()),
        "insumo_id": insumo(api),
        "tipo": "entrada",
        "data": HOJE,
        "quantidade": 1.2345,
        "valor_unitario": 0.01235,
    }

    primeira = api.post("/movimentacoes", json=corpo)
    reenvio = api.post("/movimentacoes", json=corpo)
    lote = api.post("/movimentacoes/lote", json={"movimentacoes": [corpo]})

    assert primeira.status_code == 201, primeira.text
    assert (primeira.json()["quantidade"], primeira.json()["valor_unitario"]) == (1.235, 0.0124)
    assert reenvio.status_code == 200, reenvio.text
    assert reenvio.json() == primeira.json()
    assert lote.json()["resultados"][0]["situacao"] == "ja_existia"


def test_item_que_o_banco_zeraria_e_recusado_sem_derrubar_o_lote(api: httpx.Client) -> None:
    id_ = insumo(api)

    def item(quantidade: float) -> dict[str, Any]:
        return {
            "uuid": str(uuid.uuid4()),
            "insumo_id": id_,
            "tipo": "entrada",
            "data": HOJE,
            "quantidade": quantidade,
        }

    fila = [item(5), item(0.0001), item(7)]

    primeira = api.post("/movimentacoes/lote", json={"movimentacoes": fila})
    reenvio = api.post("/movimentacoes/lote", json={"movimentacoes": fila})

    assert primeira.status_code == 200, primeira.text
    assert [r["situacao"] for r in primeira.json()["resultados"]] == [
        "gravada",
        "recusada",
        "gravada",
    ]
    assert [r["situacao"] for r in reenvio.json()["resultados"]] == [
        "ja_existia",
        "recusada",
        "ja_existia",
    ]
    assert api.get(f"/insumos/{id_}").json()["estoque_atual"] == 12


def test_cadastros_com_numero_que_o_banco_zeraria_dao_422(api: httpx.Client) -> None:
    id_ = insumo(api)
    ontem = str(hoje() - timedelta(days=1))
    compra = {"insumo_id": id_, "tipo": "entrada", "data": ontem, "quantidade": 1}

    assert api.post("/movimentacoes", json=compra | {"valor_unitario": 0.00001}).status_code == 422
    assert (
        api.post("/insumos", json={"nome": "Sal", "unidade": "kg", "embalagem": 0.0001}).status_code
        == 422
    )
    assert (
        api.put(
            f"/insumos/{id_}", json={"nome": "Ureia", "unidade": "kg", "embalagem": 0.0004}
        ).status_code
        == 422
    )
    assert api.post("/talhoes", json={"nome": "Horta", "area_ha": 0.004}).status_code == 422
    assert (
        api.post("/talhoes", json={"nome": "Canteiro", "area_ha": 0.005}).json()["area_ha"] == 0.01
    )
