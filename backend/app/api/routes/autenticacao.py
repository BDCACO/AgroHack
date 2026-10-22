from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import exigir_sessao
from app.core.database import get_db
from app.models import Sessao
from app.schemas.usuario import Entrada, PedidoDeEntrada, TrocaDeSenha, UsuarioResumo
from app.services import autenticacao as servico

# Dois routers: entrar é público (é como se consegue o token); o resto é da própria sessão.
publico = APIRouter(prefix="/auth", tags=["autenticação"])
router = APIRouter(prefix="/auth", tags=["autenticação"])


@publico.post(
    "/entrar",
    response_model=Entrada,
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Login ou senha incorretos"}},
)
def entrar(pedido: PedidoDeEntrada, db: Session = Depends(get_db)) -> Entrada:
    """Abre uma sessão e devolve o token, uma vez só: mande-o em cada pedido no cabeçalho
    `Authorization: Bearer <token>`. Vale 30 dias, a não ser que se saia antes."""
    try:
        token, sessao = servico.entrar(db, pedido.login, pedido.senha, pedido.dispositivo)
    except servico.LoginRecusado as erro:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, str(erro), headers={"WWW-Authenticate": "Bearer"}
        ) from None
    return Entrada(
        token=token,
        expira_em=sessao.expira_em,
        usuario=UsuarioResumo.model_validate(sessao.usuario),
    )


@router.post("/sair", status_code=status.HTTP_204_NO_CONTENT)
def sair(sessao: Sessao = Depends(exigir_sessao), db: Session = Depends(get_db)) -> Response:
    """Encerra a sessão deste token (as de outros aparelhos continuam)."""
    servico.sair(db, sessao)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/eu", response_model=UsuarioResumo)
def quem_sou_eu(sessao: Sessao = Depends(exigir_sessao)) -> UsuarioResumo:
    return UsuarioResumo.model_validate(sessao.usuario)


@router.put("/senha", status_code=status.HTTP_204_NO_CONTENT)
def trocar_senha(
    troca: TrocaDeSenha, sessao: Sessao = Depends(exigir_sessao), db: Session = Depends(get_db)
) -> Response:
    """Troca a própria senha (mínimo de 8 caracteres) e encerra as sessões dos outros
    aparelhos; a deste continua."""
    try:
        servico.trocar_senha(db, sessao, troca.senha_atual, troca.senha_nova)
    except servico.SenhaAtualIncorreta:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual não confere.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
