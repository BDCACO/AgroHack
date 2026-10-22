"""Lançamento offline do app: o identificador gerado no celular (`uuid`) torna o envio
repetível sem duplicar, e o lote (`POST /movimentacoes/lote`) manda a fila inteira de uma
vez, item a item. Banco de teste: SQLite."""

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.models import Movimentacao
from app.services import estoque as servico

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


def lancamento(insumo: int, **campos: Any) -> dict[str, Any]:
    return {
        "uuid": str(uuid4()),
        "insumo_id": insumo,
        "tipo": "saida",
        "data": dia(0),
        "quantidade": 2.5,
    } | campos


def test_reenvio_do_mesmo_lancamento_devolve_o_gravado_sem_duplicar(client: TestClient) -> None:
    insumo = criar_insumo(client)
    corpo = lancamento(insumo, tipo="entrada", quantidade=50, validade=dia(-90), valor_unitario=3)
    primeiro = client.post("/api/v1/movimentacoes", json=corpo)

    # A resposta se perdeu no caminho; o app manda de novo.
    segundo = client.post("/api/v1/movimentacoes", json=corpo)

    assert (primeiro.status_code, segundo.status_code) == (201, 200)
    assert segundo.json() == primeiro.json()
    assert len(client.get("/api/v1/movimentacoes").json()) == 1


def test_reenvio_reconhece_a_quantidade_como_o_banco_guardou(client: TestClient) -> None:
    # O banco guarda 3 casas: 2,0004 kg vira 2 kg, e o reenvio ainda é o mesmo lançamento.
    insumo = criar_insumo(client)
    corpo = lancamento(insumo, quantidade=2.0004)
    client.post("/api/v1/movimentacoes", json=corpo)

    assert client.post("/api/v1/movimentacoes", json=corpo).status_code == 200


def test_mesmo_uuid_com_outro_conteudo_e_conflito(client: TestClient) -> None:
    insumo = criar_insumo(client)
    corpo = lancamento(insumo)
    client.post("/api/v1/movimentacoes", json=corpo)

    resposta = client.post("/api/v1/movimentacoes", json=corpo | {"quantidade": 3})

    assert resposta.status_code == 409
    assert "quantidade" in resposta.json()["detail"]
    assert "uuid novo" in resposta.json()["detail"]
    assert len(client.get("/api/v1/movimentacoes").json()) == 1


def test_lancamentos_iguais_sem_uuid_continuam_sendo_dois(client: TestClient) -> None:
    # Duas retiradas iguais no mesmo dia existem de verdade: sem uuid, nada é deduzido.
    insumo = criar_insumo(client)
    corpo = lancamento(insumo, uuid=None)

    respostas = [client.post("/api/v1/movimentacoes", json=corpo) for _ in range(2)]

    assert [r.status_code for r in respostas] == [201, 201]
    assert len(client.get("/api/v1/movimentacoes").json()) == 2


def test_removido_e_reenviado_volta_a_ser_gravado(client: TestClient) -> None:
    insumo = criar_insumo(client)
    corpo = lancamento(insumo)
    gravado = client.post("/api/v1/movimentacoes", json=corpo).json()
    client.delete(f"/api/v1/movimentacoes/{gravado['id']}")

    resposta = client.post("/api/v1/movimentacoes", json=corpo)

    # Regra simples: o que foi removido não deixa rastro, e o reenvio grava de novo.
    assert resposta.status_code == 201
    assert len(client.get("/api/v1/movimentacoes").json()) == 1


def test_envio_simultaneo_barrado_pelo_banco_vira_reenvio(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro envio gravou entre a consulta e o INSERT deste: quem barra é o UNIQUE do
    banco, e a resposta tem de ser a do reenvio, não um 500."""
    insumo = criar_insumo(client)
    corpo = lancamento(insumo)
    client.post("/api/v1/movimentacoes", json=corpo)
    consulta = servico._pelo_uuid
    chamadas = []

    def sem_ver_o_outro_envio(db: Session, uuid: UUID) -> Movimentacao | None:
        chamadas.append(uuid)
        return None if len(chamadas) == 1 else consulta(db, uuid)

    monkeypatch.setattr(servico, "_pelo_uuid", sem_ver_o_outro_envio)

    resposta = client.post("/api/v1/movimentacoes", json=corpo)

    assert resposta.status_code == 200, resposta.json()
    assert len(chamadas) == 2
    assert len(client.get("/api/v1/movimentacoes").json()) == 1
