from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.relogio import hoje
from app.schemas.estoque import (
    AjusteDeInventario,
    ContagemDeInventario,
    InsumoCadastro,
    InsumoDetalhe,
    InsumoResposta,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PedidoDeImportacao,
    Resumo,
)
from app.services import estoque as servico
from app.services import planilha_modelo, relatorio, resumo
from app.services.importacao import ResultadoImportacao, importar

router = APIRouter(tags=["estoque"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um insumo com esse nome.")
_INSUMO_INEXISTENTE = "Insumo não encontrado."
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/insumos", response_model=list[InsumoResposta])
def listar_insumos(db: Session = Depends(get_db)) -> list[InsumoResposta]:
    """Cada insumo com o estoque atual e a análise na data de hoje (Rondônia)."""
    return servico.listar_insumos(db)


@router.get("/resumo", response_model=Resumo)
def resumir_estoque(db: Session = Depends(get_db)) -> Resumo:
    """A visão geral em reais: valor em estoque, perdas (descartes e faltas da contagem),
    custo das compras dos próximos 30 dias e alertas por gravidade, com as limitações."""
    return resumo.gerar(db)


@router.post("/insumos", response_model=InsumoResposta, status_code=status.HTTP_201_CREATED)
def criar_insumo(dados: InsumoCadastro, db: Session = Depends(get_db)) -> InsumoResposta:
    try:
        return servico.criar_insumo(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.put("/insumos/{insumo_id}", response_model=InsumoResposta)
def atualizar_insumo(
    insumo_id: int, dados: InsumoCadastro, db: Session = Depends(get_db)
) -> InsumoResposta:
    try:
        return servico.atualizar_insumo(db, insumo_id, dados)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None


@router.get("/insumos/{insumo_id}", response_model=InsumoDetalhe)
def detalhar_insumo(insumo_id: int, db: Session = Depends(get_db)) -> InsumoDetalhe:
    """O insumo com a análise de hoje, o saldo dia a dia e as movimentações."""
    try:
        return servico.detalhar_insumo(db, insumo_id)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None


@router.delete("/insumos/{insumo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_insumo(insumo_id: int, db: Session = Depends(get_db)) -> Response:
    """Remove o insumo e todas as movimentações dele."""
    try:
        servico.remover_insumo(db, insumo_id)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/insumos/{insumo_id}/inventario", response_model=AjusteDeInventario)
def registrar_inventario(
    insumo_id: int, contagem: ContagemDeInventario, db: Session = Depends(get_db)
) -> AjusteDeInventario:
    """Contagem física do galpão: lança a diferença para o saldo registrado naquele dia
    (sobra vira entrada; falta, saída), sem contar como consumo. Bateu, nada é lançado."""
    try:
        return servico.registrar_inventario(db, insumo_id, contagem)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None


@router.get("/movimentacoes", response_model=list[MovimentacaoResposta])
def listar_movimentacoes(
    insumo_id: int | None = None,
    limite: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[MovimentacaoResposta]:
    """As mais recentes primeiro."""
    return servico.listar_movimentacoes(db, insumo_id, limite)


@router.post(
    "/movimentacoes", response_model=MovimentacaoResposta, status_code=status.HTTP_201_CREATED
)
def registrar_movimentacao(
    dados: MovimentacaoEntrada, response: Response, db: Session = Depends(get_db)
) -> MovimentacaoResposta:
    """Com `uuid` (gerado pelo app), reenviar é seguro: o lançamento já gravado volta com
    `200`, sem gravar de novo; o mesmo uuid com outro conteúdo é `409`."""
    try:
        registro = servico.registrar_movimentacao(db, dados)
    except servico.InsumoInexistente:
        # 422, não 404: o recurso da URL existe; o que está errado é o corpo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INSUMO_INEXISTENTE) from None
    except servico.LancamentoDiferente as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    if not registro.nova:
        # Nada foi criado agora: 200, e não 201.
        response.status_code = status.HTTP_200_OK
    return registro.movimentacao


@router.delete("/movimentacoes/{movimentacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_movimentacao(movimentacao_id: int, db: Session = Depends(get_db)) -> Response:
    """Para corrigir lançamento errado: remove e lança de novo."""
    if not servico.remover_movimentacao(db, movimentacao_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimentação não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/importacoes", response_model=ResultadoImportacao)
def importar_planilha(
    pedido: PedidoDeImportacao, db: Session = Depends(get_db)
) -> ResultadoImportacao:
    """Movimentações de uma planilha, em `xlsx` (base64) ou `conteudo` (texto do CSV), com
    as colunas data, insumo, unidade, tipo, quantidade e validade. Sem `confirmar`, só
    confere e resume. Com um erro sequer, nada é gravado: a resposta lista os erros por
    linha e `importado` vem falso."""
    arquivo = pedido.xlsx if pedido.xlsx is not None else pedido.conteudo
    return importar(db, arquivo, confirmar=pedido.confirmar)


@router.get(
    "/importacoes/modelo.xlsx",
    response_class=Response,
    responses={200: {"content": {_XLSX: {}}, "description": "Planilha modelo"}},
)
def baixar_planilha_modelo(db: Session = Depends(get_db)) -> Response:
    """Planilha modelo formatada, com os insumos cadastrados para escolher da lista."""
    return Response(
        planilha_modelo.gerar(db),
        media_type=_XLSX,
        headers={"Content-Disposition": 'attachment; filename="modelo-campocerto.xlsx"'},
    )


@router.get(
    "/relatorio.xlsx",
    response_class=Response,
    responses={200: {"content": {_XLSX: {}}, "description": "Relatório do estoque"}},
)
def baixar_relatorio(db: Session = Depends(get_db)) -> Response:
    """Alertas, reposição, situação de cada insumo e todas as movimentações, em Excel. A
    aba Movimentações tem o formato da importação: serve de cópia de segurança."""
    return Response(
        relatorio.gerar(db),
        media_type=_XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="relatorio-campocerto-{hoje()}.xlsx"'
        },
    )
