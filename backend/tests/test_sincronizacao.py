"""Lançamento offline do app: o identificador gerado no celular (`uuid`) torna o envio
repetível sem duplicar, e o lote (`POST /movimentacoes/lote`) manda a fila inteira de uma
vez, item a item. Banco de teste: SQLite."""

from datetime import timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.relogio import hoje

HOJE = hoje()


def dia(dias_atras: int) -> str:
    return str(HOJE - timedelta(days=dias_atras))


def criar_insumo(client: TestClient, nome: str = "Ureia") -> int:
    resposta = client.post("/api/v1/insumos", json={"nome": nome, "unidade": "kg"})
    assert resposta.status_code == 201, resposta.json()
    return resposta.json()["id"]


def test_lancamento_guarda_o_uuid_do_app(client: TestClient) -> None:
    insumo = criar_insumo(client)
    identificador = str(uuid4())

    resposta = client.post(
        "/api/v1/movimentacoes",
        json={
            "uuid": identificador,
            "insumo_id": insumo,
            "tipo": "entrada",
            "data": dia(0),
            "quantidade": 10,
        },
    )

    assert resposta.status_code == 201, resposta.json()
    assert resposta.json()["uuid"] == identificador
    [listada] = client.get("/api/v1/movimentacoes").json()
    assert listada["uuid"] == identificador


def test_lancamento_sem_uuid_continua_como_antes(client: TestClient) -> None:
    insumo = criar_insumo(client)

    resposta = client.post(
        "/api/v1/movimentacoes",
        json={"insumo_id": insumo, "tipo": "entrada", "data": dia(0), "quantidade": 10},
    )

    assert resposta.status_code == 201
    assert resposta.json()["uuid"] is None
