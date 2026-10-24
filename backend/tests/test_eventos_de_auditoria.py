"""Os eventos de auditoria: o que é sensível ou destrutivo deixa rastro (quem, quando, o
quê, e o conteúdo do que foi apagado), na mesma transação da ação e sem segredo nenhum."""

from datetime import date
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EventoDeAuditoria
from app.services import auditoria


def eventos(db: Session, acao: str | None = None) -> list[EventoDeAuditoria]:
    """Os eventos gravados, na ordem em que entraram."""
    consulta = select(EventoDeAuditoria).order_by(EventoDeAuditoria.id)
    if acao is not None:
        consulta = consulta.where(EventoDeAuditoria.acao == acao)
    return list(db.scalars(consulta))


def test_registrar_grava_junto_com_a_transacao_de_quem_chamou(db: Session) -> None:
    origem = auditoria.Origem(usuario_id=None, ip="192.168.0.10", dispositivo="Celular do Zé")

    auditoria.registrar(
        db,
        origem,
        "movimentacao.removida",
        "movimentacao",
        7,
        {"data": date(2026, 10, 1), "uuid": UUID("6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e")},
    )
    # Sem commit de quem chamou, nada fica: o evento é parte da ação, e não à parte dela.
    db.rollback()
    assert eventos(db) == []

    auditoria.registrar(db, origem, "movimentacao.removida", "movimentacao", 7, {"a": 1})
    db.commit()
    [evento] = eventos(db)
    assert (evento.acao, evento.entidade, evento.entidade_id) == (
        "movimentacao.removida",
        "movimentacao",
        7,
    )
    assert (evento.origem, evento.ip, evento.dispositivo) == (
        "api",
        "192.168.0.10",
        "Celular do Zé",
    )
    assert evento.usuario_id is None
    assert evento.ocorrido_em.tzinfo is not None


def test_datas_e_uuids_viram_texto_no_json(db: Session) -> None:
    auditoria.registrar(
        db,
        auditoria.TERMINAL,
        "movimentacao.removida",
        "movimentacao",
        1,
        {"data": date(2026, 10, 1), "uuid": UUID("6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e")},
    )
    db.commit()

    [evento] = eventos(db)
    assert evento.dados == {"data": "2026-10-01", "uuid": "6f1c2a4e-8b3d-4f5a-9c7e-1d2b3a4c5d6e"}
    assert evento.origem == "terminal"


@pytest.mark.parametrize(
    "dados",
    [
        {"senha": "x"},
        {"senha_hash": "$argon2id$..."},
        {"token": "abc"},
        {"token_hash": "abc"},
        {"antes": {"senha_nova": "x"}},
        {"movimentacoes": [{"quantidade": 1, "token": "abc"}]},
    ],
)
def test_segredo_nao_entra_no_evento_nem_por_engano(db: Session, dados: dict) -> None:
    with pytest.raises(ValueError, match="segredo"):
        auditoria.registrar(db, auditoria.TERMINAL, "usuario.alterado", "usuario", 1, dados)


def test_acao_desconhecida_e_recusada(db: Session) -> None:
    # O código é estável: a tela e os filtros dependem dele. Um novo entra na lista.
    with pytest.raises(ValueError, match="ação"):
        auditoria.registrar(db, auditoria.TERMINAL, "insumo.apagado", "insumo", 1, {})
