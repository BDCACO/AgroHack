"""Fazenda de demonstração: 6 meses de movimentações FICTÍCIAS, pensadas para acender
cada tipo de alerta na apresentação, mais um insumo saudável para contraste. As compras
têm preços plausíveis (também fictícios), para os alertas e a reposição falarem em reais.
As retiradas vão para três talhões fictícios, com carências também fictícias, de modo que
um deles (o Talhão Norte) esteja em carência no dia da carga. As compras vêm de três
fornecedores fictícios (a ureia, de dois, a preços diferentes), e há um pedido a caminho:
o do sal mineral, cujo consumo disparou.

    python -m app.demo carregar   # apaga a demonstração anterior e gera de novo
    python -m app.demo limpar     # apaga só os insumos e talhões marcados como demonstração

As datas são relativas ao dia em que se carrega: rode `carregar` no dia da
apresentação, para os alertas baterem com o roteiro. Os insumos, os talhões e os
fornecedores ficam marcados (`demonstracao`), e a tela avisa que não são dados reais.
"""

import sys
from datetime import date, timedelta
from random import Random

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import Session

from app.core.database import get_sessionmaker
from app.core.relogio import hoje
from app.models import Categoria, Fornecedor, Insumo, ItemDoPedido, Movimentacao, Pedido, Talhao
from app.services import auditoria

DIAS_DE_HISTORICO = 180
TALHOES = (
    ("Talhão Norte", 120, "Soja"),
    ("Talhão Sul", 80, "Milho"),
    ("Pasto 1", 45, "Pasto"),
)
# Nomes inventados, sem telefone: não são revendas de verdade.
FORNECEDORES = (
    ("Revenda Boa Safra", "Ariquemes"),
    ("Cooperativa Vale Verde", "Ariquemes"),
    ("AgroVet Pioneiro", "Cacaulândia"),
)
# Insumo → categoria, com os nomes das de partida da migration 0011: num banco migrado,
# todas já existem, e a demonstração não cria categoria nenhuma.
CATEGORIAS = {
    "Ureia agrícola": "Fertilizante",
    "Glifosato 480": "Defensivo agrícola",
    "Calcário dolomítico": "Corretivo de solo",
    "Fungicida azoxistrobina": "Defensivo agrícola",
    "Sal mineral 80P": "Nutrição animal",
    "Ivermectina 1%": "Medicamento veterinário",
    "Semente de milho híbrido": "Semente e muda",
}


def carregar(db: Session, referencia: date) -> int:
    """Apaga a demonstração anterior e gera de novo, numa transação só: ou a fazenda
    fictícia é trocada inteira, ou nada muda. O evento diz quanto saiu e quanto entrou."""
    removidos = _apagar(db)
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
    # Como o talhão: o fornecedor que já existe com o nome é reaproveitado.
    ja_cadastrados = {
        f.nome: f
        for f in db.scalars(
            select(Fornecedor).where(Fornecedor.nome.in_([nome for nome, _ in FORNECEDORES]))
        )
    }
    fornecedores = {
        nome: ja_cadastrados.get(nome) or Fornecedor(nome=nome, cidade=cidade, demonstracao=True)
        for nome, cidade in FORNECEDORES
    }
    insumos = _fazenda(
        referencia, {nome: talhao.id for nome, talhao in talhoes.items()}, fornecedores
    )
    _categorizar(db, insumos)
    db.add_all(insumos)
    db.add(_pedido_a_caminho(referencia, insumos, fornecedores))
    criados = {
        "insumos": len(insumos),
        # Depois do flush todo talhão tem id: o criado agora é o marcado como demonstração
        # (o reaproveitado já deixou de sê-lo no _apagar, ou é real).
        "talhoes": sum(t.demonstracao for t in talhoes.values()),
        "fornecedores": sum(f.id is None for f in fornecedores.values()),
        "pedidos": 1,
    }
    auditoria.registrar(
        db,
        auditoria.TERMINAL,
        "demo.carregada",
        None,
        None,
        {"referencia": referencia, "criados": criados, "removidos": removidos},
    )
    db.commit()
    return len(insumos)


def _pedido_a_caminho(
    referencia: date, insumos: list[Insumo], fornecedores: dict[str, Fornecedor]
) -> Pedido:
    """O sal mineral, cujo consumo disparou na última semana, foi pedido ontem. Não é a
    ureia de propósito: o pedido a caminho tiraria dela o "pedir hoje" do roteiro."""
    sal = next(i for i in insumos if i.nome == "Sal mineral 80P")
    return Pedido(
        fornecedor=fornecedores["AgroVet Pioneiro"],
        situacao="aberto",
        feito_em=referencia - timedelta(days=1),
        previsto_para=referencia + timedelta(days=5),
        observacao="20 sacos de 25 kg, combinado por telefone.",
        itens=[ItemDoPedido(insumo=sal, quantidade=500, valor_unitario=4.8)],
    )


def _categorizar(db: Session, insumos: list[Insumo]) -> None:
    """Põe cada insumo na sua categoria, reaproveitando a que já existe pelo nome. Só
    marca: a categoria não entra na análise, e os alertas do roteiro não mudam. A que
    faltar (o dono a removeu, ou o banco não veio da migration) é criada; sem marca de
    demonstração, porque é uma das de partida, e o `limpar` não a apaga."""
    existentes = {
        c.nome: c
        for c in db.scalars(select(Categoria).where(Categoria.nome.in_(CATEGORIAS.values())))
    }
    for insumo in insumos:
        nome = CATEGORIAS[insumo.nome]
        insumo.categoria = existentes.setdefault(nome, Categoria(nome=nome))


def limpar(db: Session) -> None:
    removidos = _apagar(db)
    auditoria.registrar(db, auditoria.TERMINAL, "demo.limpa", None, None, {"removidos": removidos})
    db.commit()


def _apagar(db: Session) -> dict[str, int]:
    """Apaga a demonstração, sem commit, e diz quanto de cada coisa saiu."""
    # As movimentações vão junto pelo ON DELETE CASCADE, e com elas as aplicações nos
    # talhões de demonstração.
    insumos = db.execute(delete(Insumo).where(Insumo.demonstracao)).rowcount
    # Talhão de demonstração com aplicação de um insumo real (lançada durante a
    # apresentação) fica: apagá-lo levaria junto o registro de onde o insumo real foi.
    com_aplicacao = exists().where(Movimentacao.talhao_id == Talhao.id)
    talhoes = db.execute(delete(Talhao).where(Talhao.demonstracao, ~com_aplicacao)).rowcount
    # E deixa de ser demonstração: guarda dado real, e a tela não pode chamá-lo de fictício.
    db.execute(update(Talhao).where(Talhao.demonstracao).values(demonstracao=False))
    # As linhas de pedido dos insumos apagados foram junto; o pedido vazio sai também.
    pedidos = db.execute(
        delete(Pedido).where(~exists().where(ItemDoPedido.pedido_id == Pedido.id))
    ).rowcount
    # O fornecedor de demonstração com compra ou pedido real fica, pelo mesmo motivo do
    # talhão, e deixa de ser demonstração.
    com_historia = exists().where(Movimentacao.fornecedor_id == Fornecedor.id) | exists().where(
        Pedido.fornecedor_id == Fornecedor.id
    )
    fornecedores = db.execute(
        delete(Fornecedor).where(Fornecedor.demonstracao, ~com_historia)
    ).rowcount
    db.execute(update(Fornecedor).where(Fornecedor.demonstracao).values(demonstracao=False))
    return {
        "insumos": insumos,
        "talhoes": talhoes,
        "fornecedores": fornecedores,
        "pedidos": pedidos,
    }


def _fazenda(
    referencia: date, talhoes: dict[str, int], fornecedores: dict[str, Fornecedor]
) -> list[Insumo]:
    # Semente fixa: a mesma fazenda a cada carga, só deslocada no calendário.
    sorteio = Random(2026)  # noqa: S311 — variação de dado fictício, não segredo
    inicio = DIAS_DE_HISTORICO - 1

    def entrada(
        dias_atras: int,
        quantidade: float,
        vence_em: int | None = None,
        *,
        valor: float,
        de: str,
    ) -> Movimentacao:
        validade = None if vence_em is None else referencia + timedelta(days=vence_em)
        return Movimentacao(
            tipo="entrada",
            data=referencia - timedelta(days=dias_atras),
            quantidade=quantidade,
            validade=validade,
            valor_unitario=valor,
            fornecedor=fornecedores[de],
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
        saldo: float, movimentacoes: list[Movimentacao], *, valor: float, de: str
    ) -> list[Movimentacao]:
        """Abre o histórico com o estoque inicial (comprado a `valor`, do fornecedor `de`)
        que faz o saldo de hoje dar `saldo`."""
        liquido = sum(m.quantidade if m.tipo == "entrada" else -m.quantidade for m in movimentacoes)
        return [entrada(inicio, round(saldo - liquido, 1), valor=valor, de=de), *movimentacoes]

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
                    entrada(75, 1000, valor=3.3, de="Revenda Boa Safra"),
                    *saidas(de=inicio, ate=90, a_cada=1, quantidade=4),
                    *saidas(de=89, ate=0, a_cada=1, quantidade=12),
                ],
                valor=2.9,
                de="Cooperativa Vale Verde",
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
                entrada(inicio, 260, vence_em=20, valor=28, de="Revenda Boa Safra"),
                entrada(40, 100, vence_em=400, valor=31.5, de="Revenda Boa Safra"),
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
                de="Cooperativa Vale Verde",
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
                25,
                saidas(de=160, ate=95, a_cada=32, quantidade=5),
                valor=165,
                de="Revenda Boa Safra",
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
                de="AgroVet Pioneiro",
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
                entrada(inicio, 15, vence_em=-12, valor=89, de="AgroVet Pioneiro"),
                entrada(30, 5, vence_em=300, valor=96, de="AgroVet Pioneiro"),
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
                80,
                saidas(de=44, ate=0, a_cada=1, quantidade=2),
                valor=980,
                de="Cooperativa Vale Verde",
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
            print(
                f"Demonstração carregada: {insumos} insumos, {len(TALHOES)} talhões e "
                f"{len(FORNECEDORES)} fornecedores fictícios, com um pedido a caminho."
            )
        else:
            limpar(db)
            print("Dados de demonstração apagados.")


if __name__ == "__main__":
    main()
