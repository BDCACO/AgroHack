from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import exigir_sessao, ip_do_pedido, origem_do_pedido
from app.api.protecoes import anotar_o_usuario, frase_de_espera
from app.core.database import get_db
from app.core.limite_de_taxa import LimiteDeTaxa
from app.core.relogio import agora
from app.models import Sessao
from app.schemas.usuario import Entrada, PedidoDeEntrada, TrocaDeSenha, UsuarioResumo
from app.services import auditoria
from app.services import autenticacao as servico
from app.services.auditoria import Origem

# Dois routers: entrar é público (é como se consegue o token); o resto é da própria sessão.
publico = APIRouter(prefix="/auth", tags=["autenticação"])
router = APIRouter(prefix="/auth", tags=["autenticação"])


def limitar_as_tentativas(request: Request, db: Session = Depends(get_db)) -> None:
    """O limite de tentativas de login por IP (`LIMITE_LOGIN_POR_MINUTO` e `_POR_HORA`),
    antes de conferir a senha: o 429 não gasta o hash lento, não conta como erro do usuário
    (senão quem passa do limite ainda bloquearia o login de alguém com tentativas que nem
    foram conferidas) e não grava `login.recusado`. Só a primeira recusa de cada rodada vai
    para a trilha (`login.limitado`), para o dono ver de onde tentaram; quem insiste não
    enche a trilha."""
    limite: LimiteDeTaxa | None = request.app.state.limite_de_login
    if limite is None:
        return
    ip = ip_do_pedido(request)
    recusa = limite.tentar(ip or "desconhecido")
    if recusa is None:
        return
    if recusa.primeira:
        auditoria.registrar(
            db,
            Origem(ip=ip),
            "login.limitado",
            None,
            None,
            {
                "limite": recusa.janela.limite,
                "janela_segundos": recusa.janela.segundos,
                "liberado_em": agora() + timedelta(seconds=recusa.espere),
            },
        )
        db.commit()
    raise HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        frase_de_espera("Muitas tentativas de entrar a partir desta rede", recusa.espere),
        headers={"Retry-After": str(recusa.espere)},
    )


@publico.post(
    "/entrar",
    response_model=Entrada,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Login ou senha incorretos"},
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Tentativas demais a partir deste IP; espere o Retry-After"
        },
    },
    dependencies=[Depends(limitar_as_tentativas)],
)
def entrar(pedido: PedidoDeEntrada, request: Request, db: Session = Depends(get_db)) -> Entrada:
    """Abre uma sessão e devolve o token, uma vez só: mande-o em cada pedido no cabeçalho
    `Authorization: Bearer <token>`. Vale 30 dias, a não ser que se saia antes."""
    try:
        token, sessao = servico.entrar(
            db, pedido.login, pedido.senha, pedido.dispositivo, ip_do_pedido(request)
        )
    except servico.LoginRecusado as erro:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, str(erro), headers={"WWW-Authenticate": "Bearer"}
        ) from None
    anotar_o_usuario(request, sessao.usuario_id)
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
    troca: TrocaDeSenha,
    sessao: Sessao = Depends(exigir_sessao),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Response:
    """Troca a própria senha (mínimo de 8 caracteres) e encerra as sessões dos outros
    aparelhos; a deste continua."""
    try:
        servico.trocar_senha(db, sessao, troca.senha_atual, troca.senha_nova, origem)
    except servico.SenhaAtualIncorreta:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual não confere.") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
