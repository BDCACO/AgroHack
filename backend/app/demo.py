"""Fazenda de demonstração: 6 meses de movimentações FICTÍCIAS, pensadas para acender
cada tipo de alerta na apresentação, mais um insumo saudável para contraste. As compras
têm preços plausíveis (também fictícios), para os alertas e a reposição falarem em reais.
As retiradas vão para três talhões fictícios, com carências também fictícias, de modo que
um deles (o Talhão Norte) esteja em carência no dia da carga.

    python -m app.demo carregar   # apaga a demonstração anterior e gera de novo
    python -m app.demo limpar     # apaga só os insumos e talhões marcados como demonstração

As datas são relativas ao dia em que se carrega: rode `carregar` no dia da
apresentação, para os alertas baterem com o roteiro. Os insumos e os talhões ficam
marcados (`demonstracao`), e a tela avisa que não são dados reais.
"""

import sys
from datetime import date, timedelta
from random import Random

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import Session

from app.core.database import get_sessionmaker
from app.core.relogio import hoje
from app.models import Insumo, Movimentacao, Talhao

DIAS_DE_HISTORICO = 180
TALHOES = (
    ("Talhão Norte", 120, "Soja"),
    ("Talhão Sul", 80, "Milho"),
    ("Pasto 1", 45, "Pasto"),
)


def carregar(db: Session, referencia: date) -> int:
    limpar(db)
    # Talhão que já existe com o nome (real, ou o que o `limpar` preservou) é
    # reaproveitado: recriá-lo quebraria no nome único. As aplicações fictícias nele
    # saem no próximo `limpar`, junto com os insumos de demonstração.
    existentes = {
        t.nome: t
        for t in db.scalars(select(Talhao).where(Talhao.nome.in_([nome for nome, *_ in TALHOES])))
    }
    talhoes = {
        nome: existentes.get(nome)
        or Talhao(nome=nome, area_ha=area, cultura=cultura, demonstracao=True)
        for nome, area, cultura in TALHOES
    }
    db.add_all(talhoes.values())
    db.flush()  # as retiradas apontam para o id de cada talhão
    insumos = _fazenda(referencia, {nome: talhao.id for nome, talhao in talhoes.items()})
    db.add_all(insumos)
    db.commit()
    return len(insumos)


def limpar(db: Session) -> None:
    # As movimentações vão junto pelo ON DELETE CASCADE, e com elas as aplicações nos
    # talhões de demonstração.
    db.execute(delete(Insumo).where(Insumo.demonstracao))
    # Talhão de demonstração com aplicação de um insumo real (lançada durante a
    # apresentação) fica: apagá-lo levaria junto o registro de onde o insumo real foi.
    com_aplicacao = exists().where(Movimentacao.talhao_id == Talhao.id)
    db.execute(delete(Talhao).where(Talhao.demonstracao, ~com_aplicacao))
    # E deixa de ser demonstração: guarda dado real, e a tela não pode chamá-lo de fictício.
    db.execute(update(Talhao).where(Talhao.demonstracao).values(demonstracao=False))
    db.commit()


def _fazenda(referencia: date, talhoes: dict[str, int]) -> list[Insumo]:
    # Semente fixa: a mesma fazenda a cada carga, só deslocada no calendário.
    sorteio = Random(2026)  # noqa: S311 — variação de dado fictício, não segredo
    inicio = DIAS_DE_HISTORICO - 1

    def entrada(
        dias_atras: int, quantidade: float, vence_em: int | None = None, *, valor: float
    ) -> Movimentacao:
        validade = None if vence_em is None else referencia + timedelta(days=vence_em)
        return Movimentacao(
            tipo="entrada",
            data=referencia - timedelta(days=dias_atras),
            quantidade=quantidade,
            validade=validade,
            valor_unitario=valor,
        )

    def saidas(de: int, ate: int, a_cada: int, quantidade: float) -> list[Movimentacao]:
        """Uma retirada a cada `a_cada` dias, de `de` até `ate` dias atrás, ±15%."""
        return [
            Movimentacao(
                tipo="saida",
                data=referencia - timedelta(days=dias_atras),
                quantidade=round(quantidade * sorteio.uniform(0.85, 1.15), 1),
            )
            for dias_atras in range(de, ate - 1, -a_cada)
        ]

    def com_saldo_final(
        saldo: float, movimentacoes: list[Movimentacao], *, valor: float
    ) -> list[Movimentacao]:
        """Abre o histórico com o estoque inicial (comprado a `valor`) que faz o saldo de
        hoje dar `saldo`."""
        liquido = sum(m.quantidade if m.tipo == "entrada" else -m.quantidade for m in movimentacoes)
        return [entrada(inicio, round(saldo - liquido, 1), valor=valor), *movimentacoes]

    def insumo(
        nome: str,
        unidade: str,
        movimentacoes: list[Movimentacao],
        talhao: str | None = None,
        **cadastro,
    ) -> Insumo:
        """Com `talhao`, todas as retiradas do insumo foram aplicadas nele. Só marca: as
        quantidades e as datas, que decidem os alertas do insumo, não mudam."""
        for movimentacao in movimentacoes:
            if talhao is not None and movimentacao.tipo == "saida":
                movimentacao.talhao_id = talhoes[talhao]
        return Insumo(
            nome=nome,
            unidade=unidade,
            demonstracao=True,
            movimentacoes=movimentacoes,
            **cadastro,
        )

    return [
        # Adubação de cobertura acelerou nos últimos 3 meses: abaixo do mínimo e acaba
        # antes de a reposição chegar. Vem em sacos de 50 kg, e a última compra saiu mais
        # cara: a reposição fecha sacos e usa o custo médio das duas. Vai para o milho, e
        # adubo não tem carência.
        insumo(
            "Ureia agrícola",
            "kg",
            estoque_minimo=300,
            prazo_reposicao_dias=10,
            embalagem=50,
            carencia_dias=0,
            talhao="Talhão Sul",
            movimentacoes=com_saldo_final(
                100,
                [
                    entrada(75, 1000, valor=3.3),
                    *saidas(de=inicio, ate=90, a_cada=1, quantidade=4),
                    *saidas(de=89, ate=0, a_cada=1, quantidade=12),
                ],
                valor=2.9,
            ),
        ),
        # O lote antigo vence em 20 dias e ainda tem produto: vencimento próximo. Aplicado na
        # soja, a última vez há 2 dias, com 7 de carência: o Talhão Norte só libera daqui a
        # 5 dias. É o talhão em carência do roteiro.
        insumo(
            "Glifosato 480",
            "L",
            estoque_minimo=40,
            prazo_reposicao_dias=15,
            carencia_dias=7,
            talhao="Talhão Norte",
            movimentacoes=[
                entrada(inicio, 260, vence_em=20, valor=28),
                entrada(40, 100, vence_em=400, valor=31.5),
                *saidas(de=170, ate=0, a_cada=14, quantidade=15),
            ],
        ),
        # Comprado para a safra inteira: o estoque dura anos no ritmo atual. Vai para o
        # pasto sem carência cadastrada, de propósito: o Pasto 1 mostra a limitação.
        insumo(
            "Calcário dolomítico",
            "t",
            prazo_reposicao_dias=20,
            talhao="Pasto 1",
            movimentacoes=com_saldo_final(
                60,
                [*saidas(de=150, ate=120, a_cada=30, quantidade=2), *saidas(45, 20, 25, 2)],
                valor=190,
            ),
        ),
        # Ninguém retira há mais de 3 meses: produto parado. Aplicado na soja há tanto tempo
        # que a carência já passou; uma aplicação recente apagaria o alerta de produto parado.
        insumo(
            "Fungicida azoxistrobina",
            "L",
            prazo_reposicao_dias=15,
            carencia_dias=30,
            talhao="Talhão Norte",
            movimentacoes=com_saldo_final(
                25, saidas(de=160, ate=95, a_cada=32, quantidade=5), valor=165
            ),
        ),
        # Consumo estável e, na última semana, quatro retiradas grandes: consumo incomum.
        insumo(
            "Sal mineral 80P",
            "kg",
            estoque_minimo=150,
            prazo_reposicao_dias=7,
            carencia_dias=0,
            talhao="Pasto 1",
            movimentacoes=com_saldo_final(
                700,
                [
                    *saidas(de=inicio, ate=8, a_cada=3, quantidade=25),
                    *saidas(de=6, ate=0, a_cada=2, quantidade=60),
                ],
                valor=4.6,
            ),
        ),
        # Lote vencido há 12 dias ainda na prateleira; o lote novo está em dia. Aplicada no
        # gado, sem talhão: a carência para o abate fica no cadastro. Num talhão, a última
        # dose (há 5 dias) poria também o Pasto 1 em carência, e o roteiro tem um só.
        insumo(
            "Ivermectina 1%",
            "L",
            estoque_minimo=2,
            prazo_reposicao_dias=10,
            carencia_dias=35,
            movimentacoes=[
                entrada(inicio, 15, vence_em=-12, valor=89),
                entrada(30, 5, vence_em=300, valor=96),
                *saidas(de=170, ate=5, a_cada=15, quantidade=1),
            ],
        ),
        # Plantio em andamento, estoque e prazo em dia: sem alertas, para contraste.
        insumo(
            "Semente de milho híbrido",
            "sc",
            estoque_minimo=10,
            prazo_reposicao_dias=20,
            carencia_dias=0,
            talhao="Talhão Sul",
            movimentacoes=com_saldo_final(
                80, saidas(de=44, ate=0, a_cada=1, quantidade=2), valor=980
            ),
        ),
    ]


def main() -> None:
    acao = sys.argv[1] if len(sys.argv) > 1 else ""
    if acao not in {"carregar", "limpar"}:
        sys.exit("uso: python -m app.demo carregar|limpar")
    with get_sessionmaker()() as db:
        if acao == "carregar":
            insumos = carregar(db, hoje())
            print(f"Demonstração carregada: {insumos} insumos e {len(TALHOES)} talhões fictícios.")
        else:
            limpar(db)
            print("Dados de demonstração apagados.")


if __name__ == "__main__":
    main()
