"""A fazenda de demonstração acende o que promete — se um limiar do motor mudar, este
teste avisa que o roteiro da apresentação precisa ser revisto."""

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.relogio import hoje
from app.demo import carregar, limpar
from app.models import Movimentacao


def test_cada_insumo_acende_os_alertas_do_roteiro(client: TestClient, db: Session) -> None:
    carregar(db, hoje())

    insumos = client.get("/api/v1/insumos").json()

    assert {i["nome"]: {a["tipo"] for a in i["analise"]["alertas"]} for i in insumos} == {
        "Calcário dolomítico": {"excesso"},
        "Fungicida azoxistrobina": {"baixa_movimentacao"},
        "Glifosato 480": {"vencimento_proximo"},
        "Ivermectina 1%": {"vencido"},
        "Sal mineral 80P": {"consumo_incomum"},
        "Semente de milho híbrido": set(),
        "Ureia agrícola": {"risco_de_falta", "abaixo_do_minimo"},
    }
    assert all(i["demonstracao"] for i in insumos)


def test_limpar_apaga_so_a_demonstracao(client: TestClient, db: Session) -> None:
    real = client.post("/api/v1/insumos", json={"nome": "Adubo da fazenda", "unidade": "kg"})
    carregar(db, hoje())
    carregar(db, hoje())  # recarregar substitui, não duplica

    limpar(db)

    assert [i["nome"] for i in client.get("/api/v1/insumos").json()] == ["Adubo da fazenda"]
    assert real.json()["demonstracao"] is False
    assert db.scalar(select(func.count()).select_from(Movimentacao)) == 0
