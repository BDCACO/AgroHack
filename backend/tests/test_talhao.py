"""Regras do talhão, sem banco e com dados sintéticos: a carência dos defensivos aplicados
e o custo do que foi aplicado. As contas esperadas estão feitas à mão nos comentários."""

from datetime import date, timedelta

from app.domain.talhao import Aplicacao, carencia

REF = date(2026, 11, 3)


def antes(dias: int) -> date:
    return REF - timedelta(days=dias)


def aplicacao(dias_atras: int, insumo: str, carencia_dias: int | None, **campos) -> Aplicacao:
    return Aplicacao(
        data=antes(dias_atras),
        insumo_id=campos.pop("insumo_id", 1),
        insumo=insumo,
        unidade=campos.pop("unidade", "L"),
        quantidade=campos.pop("quantidade", 1),
        carencia_dias=carencia_dias,
        **campos,
    )


def test_em_carencia_avisa_ate_quando_nao_colher_e_por_que() -> None:
    # 28/10 + 15 dias = 12/11: hoje (03/11) ainda faltam 9 dias.
    aplicacoes = [aplicacao(6, "Fungicida X", 15)]

    resultado = carencia("Talhão Norte", aplicacoes, REF)

    assert resultado.colheita_liberada_em == date(2026, 11, 12)
    [alerta] = resultado.alertas
    assert (alerta.tipo, alerta.gravidade) == ("carencia", "alta")
    assert alerta.justificativa == (
        "Talhão Norte: não colher nem abater antes de 12/11/2026 (faltam 9 dias). "
        "Fungicida X aplicado em 28/10/2026, carência de 15 dias."
    )
    assert resultado.limitacoes == [
        "A carência é a do cadastro de cada insumo: confira na bula ou no receituário, "
        "porque ela pode mudar com a cultura."
    ]


def test_vale_a_aplicacao_que_libera_por_ultimo_e_nao_a_mais_recente() -> None:
    # A mais recente (ontem, 3 dias) libera em 05/11; a de 10 dias atrás com 30 dias de
    # carência só libera em 23/11. Vale o maior prazo.
    aplicacoes = [
        aplicacao(10, "Inseticida Y", 30),
        aplicacao(1, "Fungicida X", 3),
        aplicacao(40, "Herbicida Z", 7),
    ]

    resultado = carencia("Talhão Sul", aplicacoes, REF)

    assert resultado.colheita_liberada_em == date(2026, 11, 23)
    [alerta] = resultado.alertas
    assert "Inseticida Y aplicado em 24/10/2026, carência de 30 dias" in alerta.justificativa


def test_carencia_cumprida_libera_sem_alerta() -> None:
    # 18/10 + 15 = 02/11, ontem. E no próprio dia da liberação também já pode colher.
    resultado = carencia("Talhão Norte", [aplicacao(16, "Fungicida X", 15)], REF)
    no_dia = carencia("Talhão Norte", [aplicacao(15, "Fungicida X", 15)], REF)

    assert resultado.colheita_liberada_em == date(2026, 11, 2)
    assert resultado.alertas == []
    assert no_dia.colheita_liberada_em == REF
    assert no_dia.alertas == []


def test_libera_amanha_fala_em_um_dia() -> None:
    resultado = carencia("Pasto 1", [aplicacao(34, "Ivermectina", 35)], REF)

    assert "(falta 1 dia)" in resultado.alertas[0].justificativa


def test_aplicacao_futura_nao_entra_na_conta() -> None:
    # Lançamento com data depois da referência (a API não deixa, mas a regra não supõe).
    resultado = carencia("Talhão Norte", [aplicacao(-2, "Fungicida X", 15)], REF)

    assert resultado.colheita_liberada_em is None
    assert resultado.alertas == []


def test_insumo_sem_carencia_cadastrada_vira_limitacao() -> None:
    # Zero é "não tem carência", como a ureia: não pede nada. Vazio é "não sei".
    aplicacoes = [
        aplicacao(2, "Ureia", 0),
        aplicacao(3, "Calcário", None),
        aplicacao(5, "Calcário", None),
        aplicacao(4, "Adubo foliar", None),
    ]

    resultado = carencia("Talhão Sul", aplicacoes, REF)

    assert resultado.colheita_liberada_em == antes(2)  # a ureia, sem prazo
    assert resultado.alertas == []
    assert resultado.limitacoes == [
        "2 insumos aplicados sem carência cadastrada (Adubo foliar, Calcário): o prazo deles "
        "não é considerado. Cadastre a carência na tela de Insumos (0 se não tem)."
    ]


def test_um_insumo_sem_carencia_no_singular() -> None:
    resultado = carencia("Pasto 1", [aplicacao(3, "Calcário", None)], REF)

    assert resultado.colheita_liberada_em is None
    assert resultado.limitacoes == [
        "1 insumo aplicado sem carência cadastrada (Calcário): o prazo dele não é "
        "considerado. Cadastre a carência na tela de Insumos (0 se não tem)."
    ]


def test_talhao_sem_aplicacao_nao_tem_o_que_dizer() -> None:
    resultado = carencia("Talhão Novo", [], REF)

    assert (resultado.colheita_liberada_em, resultado.alertas, resultado.limitacoes) == (
        None,
        [],
        [],
    )
