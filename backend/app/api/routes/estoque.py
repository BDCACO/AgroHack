from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido, usuario_atual
from app.api.routes.talhoes import Periodo
from app.core.database import get_db
from app.core.relogio import hoje
from app.models import Usuario
from app.schemas.estoque import (
    AjusteDeInventario,
    ContagemDeInventario,
    InsumoCadastro,
    InsumoDetalhe,
    InsumoResposta,
    LoteDeMovimentacoes,
    MovimentacaoEntrada,
    MovimentacaoResposta,
    PedidoDeImportacao,
    ResultadoDoLote,
    Resumo,
)
from app.services import estoque as servico
from app.services import planilha_modelo, relatorio, resumo, sincronizacao
from app.services.auditoria import Origem
from app.services.importacao import ResultadoImportacao, importar

# Dois níveis (app/api/permissoes.py): o campo lê e lança, o que o funcionário faz; a gestão
# cadastra, remove e mexe com planilhas, o que é do dono.
campo = APIRouter(tags=["estoque"])
gestao = APIRouter(tags=["estoque"])

_NOME_DUPLICADO = HTTPException(status.HTTP_409_CONFLICT, "Já existe um insumo com esse nome.")
_CODIGO_DE_BARRAS_DUPLICADO = HTTPException(
    status.HTTP_409_CONFLICT, "Já existe um insumo com esse código de barras."
)
_INSUMO_INEXISTENTE = "Insumo não encontrado."
# 422, e não 404: o insumo da URL existe; o que está errado é o corpo.
_CATEGORIA_INEXISTENTE = HTTPException(
    status.HTTP_422_UNPROCESSABLE_CONTENT, "Categoria não encontrada."
)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@campo.get("/insumos", response_model=list[InsumoResposta])
def listar_insumos(
    categoria_id: int | None = None,
    busca: str | None = Query(None, min_length=1, max_length=120),
    gravidade: Literal["alta", "media", "baixa"] | None = None,
    com_alerta: bool | None = None,
    db: Session = Depends(get_db),
) -> list[InsumoResposta]:
    """Cada insumo com o estoque atual e a análise na data de hoje (Rondônia). Filtros
    opcionais, que se somam: `categoria_id`; `busca` no nome, sem diferenciar maiúsculas nem
    acentos; `gravidade`, quem tem algum alerta dela; `com_alerta`, quem tem (ou não) algum."""
    return servico.listar_insumos(db, categoria_id, busca, gravidade, com_alerta)


@campo.get("/resumo", response_model=Resumo)
def resumir_estoque(db: Session = Depends(get_db)) -> Resumo:
    """A visão geral em reais: valor em estoque, perdas (descartes e faltas da contagem),
    custo das compras dos próximos 30 dias e alertas por gravidade, com as limitações."""
    return resumo.gerar(db)


@gestao.post("/insumos", response_model=InsumoResposta, status_code=status.HTTP_201_CREATED)
def criar_insumo(dados: InsumoCadastro, db: Session = Depends(get_db)) -> InsumoResposta:
    try:
        return servico.criar_insumo(db, dados)
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None
    except servico.CodigoDeBarrasDuplicado:
        raise _CODIGO_DE_BARRAS_DUPLICADO from None
    except servico.CategoriaInexistente:
        raise _CATEGORIA_INEXISTENTE from None


@gestao.put("/insumos/{insumo_id}", response_model=InsumoResposta)
def atualizar_insumo(
    insumo_id: int,
    dados: InsumoCadastro,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> InsumoResposta:
    try:
        return servico.atualizar_insumo(db, insumo_id, dados, origem)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None
    except servico.NomeDuplicado:
        raise _NOME_DUPLICADO from None
    except servico.CodigoDeBarrasDuplicado:
        raise _CODIGO_DE_BARRAS_DUPLICADO from None
    except servico.CategoriaInexistente:
        raise _CATEGORIA_INEXISTENTE from None


@campo.get("/insumos/{insumo_id}", response_model=InsumoDetalhe)
def detalhar_insumo(insumo_id: int, db: Session = Depends(get_db)) -> InsumoDetalhe:
    """O insumo com a análise de hoje, o saldo dia a dia e as movimentações."""
    try:
        return servico.detalhar_insumo(db, insumo_id)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None


@gestao.delete("/insumos/{insumo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_insumo(
    insumo_id: int, db: Session = Depends(get_db), origem: Origem = Depends(origem_do_pedido)
) -> Response:
    """Remove o insumo e todas as movimentações dele. 409 se ele foi aplicado em algum
    talhão: a rastreabilidade e a carência não somem com ele. O cadastro e cada
    movimentação ficam na trilha de auditoria (`insumo.removido`)."""
    try:
        servico.remover_insumo(db, insumo_id, origem)
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None
    except servico.InsumoAplicadoEmTalhao as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@campo.post("/insumos/{insumo_id}/inventario", response_model=AjusteDeInventario)
def registrar_inventario(
    insumo_id: int,
    contagem: ContagemDeInventario,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_atual),
) -> AjusteDeInventario:
    """Contagem física do galpão: lança a diferença para o saldo registrado naquele dia
    (sobra vira entrada; falta, saída), sem contar como consumo. Bateu, nada é lançado."""
    try:
        return servico.registrar_inventario(db, insumo_id, contagem, _id(usuario))
    except servico.InsumoInexistente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, _INSUMO_INEXISTENTE) from None


@campo.get("/movimentacoes", response_model=list[MovimentacaoResposta])
def listar_movimentacoes(
    response: Response,
    insumo_id: int | None = None,
    tipo: Literal["entrada", "saida"] | None = None,
    motivo: Literal["descarte", "inventario", "nenhum"] | None = None,
    categoria_id: int | None = None,
    talhao_id: int | None = None,
    fornecedor_id: int | None = None,
    usuario_id: int | None = None,
    periodo: Periodo = Depends(),
    busca: str | None = Query(None, min_length=1, max_length=120),
    limite: int = Query(200, ge=1, le=1000),
    deslocamento: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[MovimentacaoResposta]:
    """As mais recentes primeiro (no mesmo dia, a lançada por último). Filtros opcionais, que
    se somam: `motivo=nenhum` é a retirada para uso (ou, na entrada, a compra); `desde` e
    `ate`, inclusive; `busca` no nome do insumo, sem diferenciar maiúsculas nem acentos.
    Página: `limite` e `deslocamento`. O total com os mesmos filtros vem no cabeçalho
    `X-Total-Count`, e o corpo continua a lista de sempre."""
    filtro = servico.FiltroDeMovimentacoes(
        insumo_id=insumo_id,
        tipo=tipo,
        motivo=motivo,
        categoria_id=categoria_id,
        talhao_id=talhao_id,
        fornecedor_id=fornecedor_id,
        usuario_id=usuario_id,
        desde=periodo.desde,
        ate=periodo.ate,
        busca=busca,
    )
    pagina, total = servico.listar_movimentacoes(db, filtro, limite, deslocamento)
    response.headers["X-Total-Count"] = str(total)
    return pagina


@campo.post(
    "/movimentacoes", response_model=MovimentacaoResposta, status_code=status.HTTP_201_CREATED
)
def registrar_movimentacao(
    dados: MovimentacaoEntrada,
    response: Response,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_atual),
) -> MovimentacaoResposta:
    """Com `uuid` (gerado pelo app), reenviar é seguro: o lançamento já gravado volta com
    `200`, sem gravar de novo; o mesmo uuid com outro conteúdo é `409`."""
    try:
        registro = servico.registrar_movimentacao(db, dados, _id(usuario))
    except servico.InsumoInexistente:
        # 422, não 404: o recurso da URL existe; o que está errado é o corpo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, _INSUMO_INEXISTENTE) from None
    except servico.TalhaoInexistente:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Talhão não encontrado."
        ) from None
    except servico.FornecedorInexistente:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Fornecedor não encontrado."
        ) from None
    except servico.LancamentoDiferente as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None
    if not registro.nova:
        # Nada foi criado agora: 200, e não 201.
        response.status_code = status.HTTP_200_OK
    return registro.movimentacao


@campo.post("/movimentacoes/lote", response_model=ResultadoDoLote)
def sincronizar_movimentacoes(
    lote: LoteDeMovimentacoes,
    db: Session = Depends(get_db),
    usuario: Usuario | None = Depends(usuario_atual),
) -> ResultadoDoLote:
    """A fila do app (até 500 lançamentos, cada um com o seu `uuid`), gravada na ordem e item
    a item: o item ruim volta `recusada` com os erros, e os outros gravam. Reenviar o lote é
    seguro: o que já entrou volta `ja_existia`."""
    return sincronizacao.sincronizar(db, lote.movimentacoes, _id(usuario))


@gestao.delete("/movimentacoes/{movimentacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_movimentacao(
    movimentacao_id: int,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Response:
    """Para corrigir lançamento errado: remove e lança de novo. O conteúdo inteiro fica na
    trilha de auditoria (`movimentacao.removida`), o bastante para relançá-lo."""
    if not servico.remover_movimentacao(db, movimentacao_id, origem):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movimentação não encontrada.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@gestao.post("/importacoes", response_model=ResultadoImportacao)
def importar_planilha(
    pedido: PedidoDeImportacao,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> ResultadoImportacao:
    """Movimentações de uma planilha, em `xlsx` (base64) ou `conteudo` (texto do CSV), com
    as colunas data, insumo, unidade, tipo, quantidade e validade. Sem `confirmar`, só
    confere e resume. Com um erro sequer, nada é gravado: a resposta lista os erros por
    linha e `importado` vem falso. A importação confirmada deixa o resumo na trilha de
    auditoria (`importacao.confirmada`)."""
    arquivo = pedido.xlsx if pedido.xlsx is not None else pedido.conteudo
    return importar(db, arquivo, confirmar=pedido.confirmar, origem=origem)


@gestao.get(
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


@gestao.get(
    "/relatorio.xlsx",
    response_class=Response,
    responses={200: {"content": {_XLSX: {}}, "description": "Relatório do estoque"}},
)
def baixar_relatorio(db: Session = Depends(get_db)) -> Response:
    """Alertas, reposição, situação de cada insumo, talhões (carência e custo) e todas as
    movimentações, em Excel. A aba Movimentações tem o formato da importação: serve de cópia
    de segurança, com o talhão de cada aplicação."""
    return Response(
        relatorio.gerar(db),
        media_type=_XLSX,
        headers={
            "Content-Disposition": f'attachment; filename="relatorio-campocerto-{hoje()}.xlsx"'
        },
    )


def _id(usuario: Usuario | None) -> int | None:
    """Quem lança, para a auditoria; None sem login (autenticação desligada)."""
    return None if usuario is None else usuario.id
