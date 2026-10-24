from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.permissoes import origem_do_pedido
from app.core.database import get_db
from app.models import Usuario
from app.schemas.usuario import (
    RedefinicaoDeSenha,
    UsuarioAlteracao,
    UsuarioCadastro,
    UsuarioResposta,
)
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
