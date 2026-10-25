from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido, sessao_atual
from app.api.routes.autenticacao import SESSAO_INEXISTENTE, lista_de_sessoes
from app.core.database import get_db
from app.models import Sessao, Usuario
from app.schemas.usuario import (
    RedefinicaoDeSenha,
    SessaoResposta,
    SessoesEncerradas,
    UsuarioAlteracao,
    UsuarioCadastro,
    UsuarioResposta,
)
from app.services import sessoes
from app.services import usuarios as servico
from app.services.auditoria import Origem

router = APIRouter(prefix="/usuarios", tags=["usuários"])

_USUARIO_INEXISTENTE = HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")


@router.get("", response_model=list[UsuarioResposta])
def listar_usuarios(db: Session = Depends(get_db)) -> list[Usuario]:
    return servico.listar(db)


@router.post("", response_model=UsuarioResposta, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    dados: UsuarioCadastro,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Usuario:
    """Cadastra o funcionário (ou outro dono) com a senha inicial, de 8 caracteres ou mais,
    que ele troca depois em PUT /auth/senha."""
    try:
        return servico.criar(db, dados, origem)
    except servico.LoginDuplicado:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Já existe um usuário com esse login."
        ) from None


@router.put("/{usuario_id}", response_model=UsuarioResposta)
def alterar_usuario(
    usuario_id: int,
    dados: UsuarioAlteracao,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Usuario:
    """Nome, papel e `ativo`; o que não vier fica como está. Desativar derruba as sessões
    abertas. O último dono ativo não se desativa nem vira funcionário (`409`)."""
    try:
        return servico.alterar(db, usuario_id, dados, origem)
    except servico.UsuarioInexistente:
        raise _USUARIO_INEXISTENTE from None
    except servico.UltimoDono as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro)) from None


@router.put("/{usuario_id}/senha", status_code=status.HTTP_204_NO_CONTENT)
def redefinir_senha(
    usuario_id: int,
    dados: RedefinicaoDeSenha,
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Response:
    """Senha nova para quem esqueceu (ou cuja senha vazou): derruba as sessões abertas dele
    e desfaz o bloqueio por senhas erradas."""
    try:
        servico.redefinir_senha(db, usuario_id, dados.senha_nova, origem)
    except servico.UsuarioInexistente:
        raise _USUARIO_INEXISTENTE from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Os aparelhos de cada um, para o dono: o celular perdido do funcionário se encerra sem
# desativá-lo nem trocar a senha dele, e sem derrubar os outros aparelhos.


@router.get("/{usuario_id}/sessoes", response_model=list[SessaoResposta])
def sessoes_do_usuario(
    usuario_id: int,
    sessao: Sessao | None = Depends(sessao_atual),
    db: Session = Depends(get_db),
) -> list[SessaoResposta]:
    """Onde o usuário tem login aberto: cada aparelho, o IP do login, o último uso e até
    quando vale."""
    try:
        return lista_de_sessoes(sessoes.ativas_de(db, usuario_id), sessao)
    except servico.UsuarioInexistente:
        raise _USUARIO_INEXISTENTE from None


@router.delete(
    "/{usuario_id}/sessoes/{sessao_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Usuário ou sessão ativa dele"}},
)
def encerrar_sessao_do_usuario(
    usuario_id: int,
    sessao_id: int,
    sessao: Sessao | None = Depends(sessao_atual),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> Response:
    """Encerra uma sessão do usuário (o celular perdido), e só ela: ele continua ativo, com
    a mesma senha, e os outros aparelhos dele seguem logados. Fica na trilha."""
    try:
        sessoes.encerrar_de(
            db, usuario_id, sessao_id, None if sessao is None else sessao.id, origem
        )
    except servico.UsuarioInexistente:
        raise _USUARIO_INEXISTENTE from None
    except sessoes.SessaoInexistente:
        raise SESSAO_INEXISTENTE from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{usuario_id}/sessoes/encerrar", response_model=SessoesEncerradas)
def encerrar_sessoes_do_usuario(
    usuario_id: int,
    sessao: Sessao | None = Depends(sessao_atual),
    db: Session = Depends(get_db),
    origem: Origem = Depends(origem_do_pedido),
) -> SessoesEncerradas:
    """Encerra todas as sessões do usuário sem desativá-lo nem trocar a senha, e diz
    quantas. Sobre o próprio dono, a deste pedido fica: ele não se tranca fora sem
    querer."""
    try:
        quantas = sessoes.encerrar_todas(
            db, usuario_id, None if sessao is None else sessao.id, origem
        )
    except servico.UsuarioInexistente:
        raise _USUARIO_INEXISTENTE from None
    return SessoesEncerradas(encerradas=quantas)
