from fastapi import APIRouter

from app.analysis.consumo import Analise, analisar
from app.domain.estoque import Encomenda, Insumo, Lote, Retirada
from app.schemas.analise import PedidoDeAnalise

router = APIRouter(tags=["análise"])


@router.post("/analises", response_model=Analise)
def analisar_insumo(pedido: PedidoDeAnalise) -> Analise:
    """Roda o motor de análise sobre os dados enviados, sem tocar o banco.

    Chama o motor direto, sem `services/`: não há repositório a orquestrar. Quando
    a importação existir, o painel lê do banco e devolve este mesmo `Analise`.
    """
    insumo = pedido.insumo.model_dump()
    custo_medio = insumo.pop("custo_medio")
    return analisar(
        Insumo(**insumo),
        [Retirada(**r.model_dump()) for r in pedido.retiradas],
        lotes=[Lote(**lote.model_dump()) for lote in pedido.lotes],
        registros_desde=pedido.registros_desde,
        referencia=pedido.referencia,
        custo_medio=custo_medio,
        a_caminho=[Encomenda(**e.model_dump()) for e in pedido.a_caminho],
        meses_de_safra=pedido.meses_de_safra,
    )
