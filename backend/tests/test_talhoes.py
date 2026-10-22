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


def criar_insumo(client: TestClient, nome: str = "Glifosato 480", **campos: Any) -> int:
    resposta = client.post("/api/v1/insumos", json={"nome": nome, "unidade": "L"} | campos)
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


def lancar(client: TestClient, **corpo: Any) -> Any:
    return client.post("/api/v1/movimentacoes", json=corpo)


def test_retirada_para_uso_vai_para_um_talhao(client: TestClient) -> None:
    talhao = criar_talhao(client)
    glifosato = criar_insumo(client)
    lancar(client, insumo_id=glifosato, tipo="entrada", data=dia(10), quantidade=100)

    resposta = lancar(
        client,
        insumo_id=glifosato,
        tipo="saida",
        data=dia(2),
        quantidade=15,
        talhao_id=talhao["id"],
    )
    sem_talhao = lancar(client, insumo_id=glifosato, tipo="saida", data=dia(1), quantidade=1)

    assert resposta.status_code == 201, resposta.json()
    assert resposta.json()["talhao_id"] == talhao["id"]
    assert sem_talhao.json()["talhao_id"] is None
    listadas = client.get("/api/v1/movimentacoes").json()
    assert [m["talhao_id"] for m in listadas] == [None, talhao["id"], None]
    # Para o estoque, a aplicação é uma retirada como outra qualquer.
    assert client.get(f"/api/v1/insumos/{glifosato}").json()["estoque_atual"] == 84


@pytest.mark.parametrize(
    "corpo",
    [
        {"tipo": "entrada"},
        {"tipo": "saida", "motivo": "descarte"},
    ],
)
def test_talhao_so_numa_retirada_para_uso(client: TestClient, corpo: dict[str, Any]) -> None:
    talhao = criar_talhao(client)
    glifosato = criar_insumo(client)

    resposta = lancar(
        client, insumo_id=glifosato, data=dia(1), quantidade=1, talhao_id=talhao["id"], **corpo
    )

    assert resposta.status_code == 422
    assert "talhão só se informa numa retirada para uso" in str(resposta.json())
    assert client.get("/api/v1/movimentacoes").json() == []


def test_talhao_inexistente_e_422(client: TestClient) -> None:
    glifosato = criar_insumo(client)

    resposta = lancar(
        client, insumo_id=glifosato, tipo="saida", data=dia(1), quantidade=1, talhao_id=99
    )

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Talhão não encontrado."


def test_talhao_com_aplicacao_nao_se_remove(client: TestClient) -> None:
    talhao = criar_talhao(client)
    glifosato = criar_insumo(client)
    aplicacao = lancar(
        client, insumo_id=glifosato, tipo="saida", data=dia(1), quantidade=1, talhao_id=talhao["id"]
    ).json()

    recusa = client.delete(f"/api/v1/talhoes/{talhao['id']}")

    assert recusa.status_code == 409
    assert recusa.json()["detail"] == (
        "Talhão Norte tem 1 aplicação registrada: removê-lo apagaria para onde foi cada "
        "insumo. Remova as aplicações antes, se foram lançadas por engano."
    )
    assert client.get(f"/api/v1/talhoes/{talhao['id']}").status_code == 200
    client.delete(f"/api/v1/movimentacoes/{aplicacao['id']}")
    assert client.delete(f"/api/v1/talhoes/{talhao['id']}").status_code == 204


def test_fila_do_app_lanca_no_talhao(client: TestClient) -> None:
    talhao = criar_talhao(client)
    glifosato = criar_insumo(client)
    base = {"insumo_id": glifosato, "data": dia(1), "quantidade": 1}

    resultado = client.post(
        "/api/v1/movimentacoes/lote",
        json={
            "movimentacoes": [
                base
                | {
                    "uuid": "6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e",
                    "tipo": "saida",
                    "talhao_id": talhao["id"],
                },
                base
                | {
                    "uuid": "7f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e",
                    "tipo": "saida",
                    "talhao_id": 99,
                },
                base
                | {
                    "uuid": "8f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e",
                    "tipo": "entrada",
                    "talhao_id": talhao["id"],
                },
            ]
        },
    ).json()

    gravada, inexistente, em_entrada = resultado["resultados"]
    assert gravada["situacao"] == "gravada"
    assert gravada["movimentacao"]["talhao_id"] == talhao["id"]
    assert (inexistente["situacao"], inexistente["erros"]) == (
        "recusada",
        ["O talhão 99 não existe: pode ter sido removido no site."],
    )
    assert em_entrada["situacao"] == "recusada"
    assert em_entrada["erros"] == [
        "Talhão só se informa numa retirada para uso: é onde o insumo foi aplicado."
    ]


def test_reenvio_com_outro_talhao_nao_e_o_mesmo_lancamento(client: TestClient) -> None:
    norte = criar_talhao(client)
    sul = criar_talhao(client, nome="Talhão Sul")
    glifosato = criar_insumo(client)
    corpo = {
        "uuid": "6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e",
        "insumo_id": glifosato,
        "tipo": "saida",
        "data": dia(1),
        "quantidade": 1,
        "talhao_id": norte["id"],
    }
    assert lancar(client, **corpo).status_code == 201

    assert lancar(client, **corpo).status_code == 200
    outro = lancar(client, **corpo | {"talhao_id": sul["id"]})
    assert outro.status_code == 409
    assert "talhao_id" in outro.json()["detail"]
