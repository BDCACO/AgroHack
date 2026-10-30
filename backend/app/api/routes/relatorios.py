from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.relogio import hoje
from app.domain import relatorio_por_periodo as dominio
from app.services import relatorio_por_periodo as servico
from app.services import relatorio_por_periodo_em_arquivo as arquivo

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PDF = "application/pdf"

# Do funcionário, como o /resumo: ele já lê o custo médio, o preço de cada compra e o
# preço pago a cada revenda, e estas são as mesmas contas somadas; o Excel e o PDF deste
# relatório também. O relatório do estoque em Excel, com a cópia de segurança de todas as
# movimentações, continua só do dono.
campo = APIRouter(tags=["relatórios"])


@dataclass(frozen=True)
class _Pedido:
    """O relatório do período pedido, com o recorte, para o cabeçalho dos arquivos."""

    relatorio: dominio.RelatorioPorPeriodo
    categoria_id: int | None
    insumo_id: int | None
    talhao_id: int | None
    fornecedor_id: int | None


def _gerar(
    desde: date | None = None,
    ate: date | None = None,
    agrupar: dominio.Agrupamento = "mes",
    categoria_id: int | None = None,
    insumo_id: int | None = None,
    talhao_id: int | None = None,
    fornecedor_id: int | None = None,
    db: Session = Depends(get_db),
) -> _Pedido:
    """Os mesmos parâmetros e as mesmas recusas para a tela, o Excel e o PDF."""
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
        relatorio = servico.gerar(
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
    return _Pedido(relatorio, categoria_id, insumo_id, talhao_id, fornecedor_id)


@campo.get("/relatorios/periodo", response_model=dominio.RelatorioPorPeriodo)
def relatorio_por_periodo(pedido: _Pedido = Depends(_gerar)) -> dominio.RelatorioPorPeriodo:
    """Por mês, semana (segunda a domingo) ou dia, de `desde` a `ate` (inclusive; sem eles,
    os últimos 12 meses até hoje): o consumo de cada insumo (só a retirada para uso, na
    unidade dele e em reais), o gasto nas compras com preço, as perdas (descarte e falta
    da contagem, pelo custo médio) e os totais por categoria e por fornecedor. O período
    sem movimento vem zerado. Até 400 períodos (por dia, uns 13 meses), com as datas de
    01/01/1900 a 31/12/2999."""
    return pedido.relatorio


@campo.get(
    "/relatorios/periodo.xlsx",
    response_class=Response,
    responses={200: {"content": {_XLSX: {}}, "description": "Relatório por período em Excel"}},
)
def baixar_relatorio_por_periodo_em_excel(
    pedido: _Pedido = Depends(_gerar), db: Session = Depends(get_db)
) -> Response:
    """O mesmo relatório de `GET /relatorios/periodo`, com os mesmos parâmetros, em Excel:
    resumo, cada período (com o gráfico), consumo por insumo, por categoria e por
    fornecedor, uma aba cada."""
    return _arquivo(pedido, db, arquivo.planilha, "xlsx", _XLSX)


@campo.get(
    "/relatorios/periodo.pdf",
    response_class=Response,
    responses={200: {"content": {_PDF: {}}, "description": "Relatório por período em PDF"}},
)
def baixar_relatorio_por_periodo_em_pdf(
    pedido: _Pedido = Depends(_gerar), db: Session = Depends(get_db)
) -> Response:
    """O mesmo relatório de `GET /relatorios/periodo`, com os mesmos parâmetros, em PDF A4
    para imprimir: os totais, o gráfico (até 62 períodos) e as tabelas."""
    return _arquivo(pedido, db, arquivo.pdf, "pdf", _PDF)


def _arquivo(
    pedido: _Pedido,
    db: Session,
    gerar: Callable[[dominio.RelatorioPorPeriodo, list[str], date], bytes],
    extensao: str,
    tipo: str,
) -> Response:
    filtros = arquivo.filtros_em_texto(
        db,
        categoria_id=pedido.categoria_id,
        insumo_id=pedido.insumo_id,
        talhao_id=pedido.talhao_id,
        fornecedor_id=pedido.fornecedor_id,
    )
    nome = arquivo.nome_do_arquivo(pedido.relatorio, extensao)
    return Response(
        gerar(pedido.relatorio, filtros, hoje()),
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
