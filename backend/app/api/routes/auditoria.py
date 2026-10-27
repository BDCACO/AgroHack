from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.routes.talhoes import Periodo
from app.core.database import get_db
from app.models import EventoDeAuditoria
from app.schemas.auditoria import EventoResposta
from app.services import auditoria as servico

# Só o dono, e sempre com login (app/api/router.py): a trilha diz quem tentou entrar e de
# onde, como a lista de usuários.
router = APIRouter(tags=["auditoria"])


@router.get("/auditoria", response_model=list[EventoResposta])
def listar_eventos(
    response: Response,
    acao: str | None = Query(None, min_length=1, max_length=40),
    usuario_id: int | None = None,
    entidade: str | None = Query(None, min_length=1, max_length=20),
    entidade_id: int | None = None,
    periodo: Periodo = Depends(),
    limite: int = Query(200, ge=1, le=1000),
    deslocamento: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[EventoDeAuditoria]:
    """O que de sensível ou destrutivo aconteceu, os mais recentes primeiro: quem fez,
    quando, de onde e, em `dados`, o conteúdo do que foi apagado ou o antes e o depois do
    que mudou. Filtros opcionais, que se somam: `acao` (o código, como `usuario.criado`, ou
    o grupo, como `usuario`), `usuario_id` (quem fez), `entidade` e `entidade_id` (sobre o
    quê), `desde` e `ate` (dias, inclusive). Página: `limite` e `deslocamento`; o total com
    os mesmos filtros vem no cabeçalho `X-Total-Count`."""
    filtro = servico.FiltroDeEventos(
        acao=acao,
        usuario_id=usuario_id,
        entidade=entidade,
        entidade_id=entidade_id,
        desde=periodo.desde,
        ate=periodo.ate,
    )
    try:
        pagina, total = servico.listar(db, filtro, limite, deslocamento)
    except servico.AcaoDesconhecida as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(erro)) from None
    response.headers["X-Total-Count"] = str(total)
    return pagina
