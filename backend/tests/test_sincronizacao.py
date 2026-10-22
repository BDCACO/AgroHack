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


def sincronizar(client: TestClient, itens: list[Any]) -> dict[str, Any]:
    resposta = client.post("/api/v1/movimentacoes/lote", json={"movimentacoes": itens})
    assert resposta.status_code == 200, resposta.json()
    return resposta.json()


def test_fila_do_app_grava_na_ordem_e_o_reenvio_nao_duplica(client: TestClient) -> None:
    insumo = criar_insumo(client)
    fila = [
        lancamento(insumo, tipo="entrada", data=dia(3), quantidade=100, valor_unitario=3.2),
        lancamento(insumo, data=dia(2), quantidade=10),
        lancamento(insumo, data=dia(1), quantidade=15.5),
    ]

    primeiro = sincronizar(client, fila)
    # A resposta não chegou ao celular: a fila inteira vai de novo.
    segundo = sincronizar(client, fila)

    assert [r["uuid"] for r in primeiro["resultados"]] == [i["uuid"] for i in fila]
    assert [r["situacao"] for r in primeiro["resultados"]] == ["gravada"] * 3
    assert primeiro["resumo"] == {"gravadas": 3, "ja_existiam": 0, "recusadas": 0}
    assert [r["situacao"] for r in segundo["resultados"]] == ["ja_existia"] * 3
    assert segundo["resumo"] == {"gravadas": 0, "ja_existiam": 3, "recusadas": 0}
    assert [r["movimentacao"] for r in segundo["resultados"]] == [
        r["movimentacao"] for r in primeiro["resultados"]
    ]
    assert primeiro["resultados"][0]["movimentacao"]["valor_unitario"] == 3.2
    assert primeiro["resultados"][0]["erros"] == []
    [listado] = client.get("/api/v1/insumos").json()
    assert listado["estoque_atual"] == 74.5


def test_item_ruim_e_recusado_e_os_outros_gravam(client: TestClient) -> None:
    insumo = criar_insumo(client)
    ja_usado = lancamento(insumo)
    sincronizar(client, [ja_usado])
    sem_uuid = lancamento(insumo)
    del sem_uuid["uuid"]
    fila = [
        lancamento(insumo, tipo="entrada", quantidade=40),
        lancamento(insumo, quantidade=-3),
        sem_uuid,
        lancamento(insumo, data="31/10/2026", tipo="troca"),
        lancamento(insumo, data=dia(-5)),
        lancamento(insumo, insumo_id=999),
        ja_usado | {"quantidade": 9},
        "não é um lançamento",
        lancamento(insumo, uuid="123"),
        lancamento(insumo, quantidade=4),
    ]

    resultado = sincronizar(client, fila)

    situacoes = [r["situacao"] for r in resultado["resultados"]]
    assert situacoes == ["gravada"] + ["recusada"] * 8 + ["gravada"]
    assert resultado["resumo"] == {"gravadas": 2, "ja_existiam": 0, "recusadas": 8}
    erros = [r["erros"] for r in resultado["resultados"][1:-1]]
    assert erros == [
        ["quantidade tem de ser maior que 0."],
        ["Falta o campo uuid, que o app gera para cada lançamento."],
        [
            "tipo tem de ser 'entrada' ou 'saida'.",
            "data não é uma data válida: use AAAA-MM-DD.",
        ],
        ["A data da movimentação não pode ser futura."],
        ["O insumo 999 não existe: pode ter sido removido no site."],
        [
            "Este uuid já identifica outro lançamento, diferente deste em: quantidade. Cada "
            "lançamento precisa de um uuid novo."
        ],
        [
            "O item não é um lançamento: mande um objeto com uuid, insumo_id, tipo, data e "
            "quantidade."
        ],
        ["uuid não é um identificador válido: gere um UUID v4 para cada lançamento."],
    ]
    assert all(r["movimentacao"] is None for r in resultado["resultados"][1:-1])
    # O uuid que dá para ler volta, para o app achar o item; o que não dá, volta vazio.
    assert resultado["resultados"][1]["uuid"] == fila[1]["uuid"]
    assert [resultado["resultados"][i]["uuid"] for i in (2, 7, 8)] == [None] * 3
    [listado] = client.get("/api/v1/insumos").json()
    assert listado["estoque_atual"] == 40 - 2.5 - 4


def test_lote_cabe_500_lancamentos_e_recusa_mais(client: TestClient) -> None:
    insumo = criar_insumo(client)
    fila = [lancamento(insumo, tipo="entrada", quantidade=1) for _ in range(500)]

    resultado = sincronizar(client, fila)
    demais = client.post(
        "/api/v1/movimentacoes/lote", json={"movimentacoes": [*fila, lancamento(insumo)]}
    )

    assert resultado["resumo"]["gravadas"] == 500
    # Pedido malformado como um todo, não um item: o app divide a fila em lotes de 500.
    assert demais.status_code == 422
