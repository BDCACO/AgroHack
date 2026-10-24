"""Regras de saldo — domínio puro, sem banco."""

from decimal import Decimal

import pytest

from app.domain.erros import EstoqueInsuficiente
from app.domain.estoque import (
    TipoMovimentacao,
    efeito_no_saldo,
    validar_inclusao,
    validar_remocao,
)

COMPRA = TipoMovimentacao.COMPRA
RETIRADA = TipoMovimentacao.RETIRADA


def test_compra_soma_e_retirada_subtrai() -> None:
    assert efeito_no_saldo(COMPRA, Decimal(10)) == Decimal(10)
    assert efeito_no_saldo(RETIRADA, Decimal(10)) == Decimal(-10)


def test_retirada_ate_o_saldo_e_aceita() -> None:
    validar_inclusao(Decimal(10), RETIRADA, Decimal(10), "kg")


def test_retirada_acima_do_saldo_e_recusada_com_explicacao() -> None:
    with pytest.raises(EstoqueInsuficiente) as erro:
        validar_inclusao(Decimal("1250.5"), RETIRADA, Decimal(2000), "kg")

    assert erro.value.mensagem == (
        "Retirada de 2.000 kg maior que o saldo disponível (1.250,5 kg)."
    )


def test_compra_nunca_e_recusada_por_saldo() -> None:
    validar_inclusao(Decimal(0), COMPRA, Decimal(5), "L")


def test_remover_retirada_sempre_pode() -> None:
    validar_remocao(Decimal(0), RETIRADA, Decimal(5), "L")


def test_remover_compra_ja_consumida_e_recusado() -> None:
    # Comprou 10, retirou 8: saldo 2. Remover a compra deixaria -8.
    with pytest.raises(EstoqueInsuficiente):
        validar_remocao(Decimal(2), COMPRA, Decimal(10), "L")


def test_remover_compra_intacta_pode() -> None:
    validar_remocao(Decimal(10), COMPRA, Decimal(10), "L")
