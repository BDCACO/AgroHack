"""Regras do talhão: até quando não se pode colher (a carência dos defensivos aplicados) e
quanto custou o que foi aplicado nele.

Puras, como as do estoque: sem I/O, sem banco, sem relógio. A data de referência entra
como parâmetro.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.domain.estoque import Alerta, dias_legivel


@dataclass(frozen=True)
class Aplicacao:
    """Uma retirada para uso lançada num talhão: o insumo foi aplicado ali."""

    data: date
    insumo_id: int
    insumo: str
    unidade: str
    quantidade: float
    # Dias mínimos entre aplicar e colher ou abater, da bula. 0 = o insumo não tem carência
    # (a ureia); None = não cadastrada, e então o prazo dele não é conhecido.
    carencia_dias: int | None = None


@dataclass(frozen=True)
class Carencia:
    # Quando a última carência acaba: max(data + carência) entre as aplicações com carência
    # cadastrada. None se nenhuma tem.
    colheita_liberada_em: date | None
    alertas: list[Alerta]
    limitacoes: list[str]


def carencia(talhao: str, aplicacoes: Iterable[Aplicacao], referencia: date) -> Carencia:
    """A colheita fica liberada quando a ÚLTIMA carência acaba, e não a da aplicação mais
    recente: um inseticida de 30 dias aplicado há 10 prende o talhão mais que um fungicida
    de 3 dias aplicado ontem.

    Enquanto não libera, o alerta é sempre de gravidade alta. Colher antes é proibido, e o
    erro não tem conserto: resíduo no alimento, carga recusada, multa. Não há meio-termo
    entre proibido e permitido, e não se sabe quando o produtor pretende colher, então a
    distância até a liberação não diminui o risco.
    """
    # A aplicação depois da referência ainda não aconteceu, para esta conta.
    feitas = [a for a in aplicacoes if a.data <= referencia]
    com_prazo = [a for a in feitas if a.carencia_dias is not None]
    limitacoes = []
    if sem_prazo := sorted({a.insumo for a in feitas if a.carencia_dias is None}):
        quantos = len(sem_prazo)
        sujeito = "1 insumo aplicado" if quantos == 1 else f"{quantos} insumos aplicados"
        dele = "dele" if quantos == 1 else "deles"
        limitacoes.append(
            f"{sujeito} sem carência cadastrada ({', '.join(sem_prazo)}): o prazo {dele} não é "
            "considerado. Cadastre a carência na tela de Insumos (0 se não tem)."
        )
    if not com_prazo:
        return Carencia(None, [], limitacoes)

    # Empate na data de liberação: vale a aplicação mais recente, a que o produtor lembra.
    decisiva = max(com_prazo, key=lambda a: (_liberada(a), a.data, a.insumo))
    liberada = _liberada(decisiva)
    alertas = []
    if liberada > referencia:
        faltam = (liberada - referencia).days
        falta = "falta" if faltam == 1 else "faltam"
        alertas.append(
            Alerta(
                "carencia",
                "alta",
                f"{talhao}: não colher nem abater antes de {liberada:%d/%m/%Y} ({falta} "
                f"{dias_legivel(faltam)}). {decisiva.insumo} aplicado em "
                f"{decisiva.data:%d/%m/%Y}, carência de {dias_legivel(decisiva.carencia_dias)}.",
            )
        )
    if any(a.carencia_dias for a in com_prazo):
        limitacoes.append(
            "A carência é a do cadastro de cada insumo: confira na bula ou no receituário, "
            "porque ela pode mudar com a cultura."
        )
    return Carencia(liberada, alertas, limitacoes)


def _liberada(aplicacao: Aplicacao) -> date:
    # No dia data + carência o intervalo mínimo já se cumpriu: dali em diante pode colher.
    return aplicacao.data + timedelta(days=aplicacao.carencia_dias)
