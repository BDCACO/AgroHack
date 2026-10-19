from fastapi import APIRouter

from app.analysis.consumo import Analise, analisar
from app.domain.estoque import Insumo, Lote, Retirada
from app.schemas.analise import PedidoDeAnalise

router = APIRouter(tags=["análise"])


@router.post("/analises", response_model=Analise)
def analisar_insumo(pedido: PedidoDeAnalise) -> Analise:
    """Roda o motor de análise sobre os dados enviados, sem tocar o banco.

    Chama o motor direto, sem `services/`: não há repositório a orquestrar. Quando
    a importação existir, o painel lê do banco e devolve este mesmo `Analise`.
    """
    return analisar(
        Insumo(**pedido.insumo.model_dump()),
        [Retirada(**r.model_dump()) for r in pedido.retiradas],
        lotes=[Lote(**lote.model_dump()) for lote in pedido.lotes],
        registros_desde=pedido.registros_desde,
        referencia=pedido.referencia,
    )
