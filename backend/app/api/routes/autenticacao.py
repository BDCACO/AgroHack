from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import exigir_sessao, ip_do_pedido, origem_do_pedido
from app.api.protecoes import anotar_o_usuario, frase_de_espera
from app.core.database import get_db
from app.core.limite_de_taxa import LimiteDeTaxa
from app.core.relogio import agora
from app.models import Sessao
from app.schemas.usuario import (
    AlteracaoDoPerfil,
    Entrada,
    PedidoDeEntrada,
    SessaoResposta,
    SessoesEncerradas,
    TrocaDeSenha,
    UsuarioResumo,
)
from app.services import auditoria, sessoes
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


@router.put("/eu", response_model=UsuarioResumo)
def alterar_meu_perfil(
    dados: AlteracaoDoPerfil,
    sessao: Sessao = Depends(exigir_sessao),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> UsuarioResumo:
    """O próprio nome e o próprio login; o que não vier fica como está. O login novo pede
    `senha_atual` (errar conta como tentativa de login). O papel não muda por aqui: só o
    dono, em Usuários."""
    try:
        usuario = servico.alterar_perfil(
            db, sessao, dados.nome, dados.login, dados.senha_atual, origem
        )
    except servico.SenhaAtualFaltando:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Para trocar o login, confirme com a senha atual."
        ) from None
    except servico.SenhaAtualIncorreta:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A senha atual não confere.") from None
    except servico.LoginEmUso:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe um usuário com esse login."
        ) from None
    return UsuarioResumo.model_validate(usuario)


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


def lista_de_sessoes(lista: list[Sessao], atual: Sessao | None) -> list[SessaoResposta]:
    """As sessões na resposta, com `atual` marcando a deste pedido."""
    atual_id = None if atual is None else atual.id
    return [
        SessaoResposta.model_validate(s).model_copy(update={"atual": s.id == atual_id})
        for s in lista
    ]


SESSAO_INEXISTENTE = HTTPException(
    status.HTTP_404_NOT_FOUND, "Sessão não encontrada: pode já ter sido encerrada ou vencido."
)


@router.get("/sessoes", response_model=list[SessaoResposta])
def minhas_sessoes(
    sessao: Sessao = Depends(exigir_sessao), db: Session = Depends(get_db)
) -> list[SessaoResposta]:
    """Onde há login aberto com o seu usuário: cada aparelho, o IP do login, o último uso
    (anotado de 5 em 5 minutos) e até quando vale. `atual` é a deste pedido."""
    return lista_de_sessoes(sessoes.ativas(db, sessao.usuario_id), sessao)


@router.delete(
    "/sessoes/{sessao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Não há essa sessão ativa sua"}},
)
def encerrar_sessao(
    sessao_id: int,
    sessao: Sessao = Depends(exigir_sessao),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Response:
    """Encerra uma sessão sua (o celular perdido), e só ela: os outros aparelhos
    continuam. A de outro usuário é `404`, como a que não existe. Encerrar a deste pedido
    é o mesmo que sair."""
    try:
        sessoes.encerrar(db, sessao.usuario_id, sessao_id, sessao.id, origem)
    except sessoes.SessaoInexistente:
        raise SESSAO_INEXISTENTE from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sessoes/encerrar-outras", response_model=SessoesEncerradas)
def encerrar_as_outras(
    sessao: Sessao = Depends(exigir_sessao),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> SessoesEncerradas:
    """Encerra todas as suas sessões menos a deste pedido, sem trocar a senha, e diz
    quantas."""
    return SessoesEncerradas(
        encerradas=sessoes.encerrar_todas(db, sessao.usuario_id, sessao.id, origem)
    )
