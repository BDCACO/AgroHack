from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.relogio import hoje
from app.domain import relatorio_por_periodo as dominio
from app.services import relatorio_por_periodo as servico

# Do funcionário, como o /resumo: ele já lê o custo médio, o preço de cada compra e o
# preço pago a cada revenda, e estas são as mesmas contas somadas. O relatório em Excel,
# com a cópia de segurança, continua só do dono.
campo = APIRouter(tags=["relatórios"])


@campo.get("/relatorios/periodo", response_model=dominio.RelatorioPorPeriodo)
def relatorio_por_periodo(
    desde: date | None = None,
    ate: date | None = None,
    agrupar: dominio.Agrupamento = "mes",
    categoria_id: int | None = None,
    insumo_id: int | None = None,
    talhao_id: int | None = None,
    fornecedor_id: int | None = None,
    db: Session = Depends(get_db),
) -> dominio.RelatorioPorPeriodo:
    """Por mês, semana (segunda a domingo) ou dia, de `desde` a `ate` (inclusive; sem eles,
    os últimos 12 meses até hoje): o consumo de cada insumo (só a retirada para uso, na
    unidade dele e em reais), o gasto nas compras com preço, as perdas (descarte e falta
    da contagem, pelo custo médio) e os totais por categoria e por fornecedor. O período
    sem movimento vem zerado. Até 400 períodos (por dia, uns 13 meses), com as datas de
    01/01/1900 a 31/12/2999."""
    ate = ate or hoje()
    try:
        # O `ate` antes de contar os doze meses para trás: a partir do ano 1, seria o ano 0.
        dominio.conferir_a_faixa(ate)
        desde = desde or max(servico.inicio_dos_ultimos_meses(ate), dominio.DATA_MINIMA)
        dominio.conferir_a_faixa(desde)
    except dominio.DataForaDaFaixa as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    if desde > ate:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "O período começa depois de terminar: troque as datas.",
        )
    try:
        return servico.gerar(
            db,
            desde,
            ate,
            agrupar,
            categoria_id=categoria_id,
            insumo_id=insumo_id,
            talhao_id=talhao_id,
            fornecedor_id=fornecedor_id,
        )
    except dominio.MuitosPeriodos as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
