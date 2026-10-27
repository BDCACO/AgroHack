"""Gestão de usuários pelo dono: cadastrar, alterar, desativar e redefinir a senha.

Usuário não se apaga: as movimentações dizem quem as lançou. Desativado, não entra, e as
sessões abertas dele caem na hora.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import senha
from app.core.relogio import agora
from app.models import Usuario
from app.schemas.usuario import UsuarioAlteracao, UsuarioCadastro
from app.services import auditoria
from app.services.autenticacao import revogar_sessoes


class LoginDuplicado(Exception):
    pass


class UsuarioInexistente(Exception):
    pass


class UltimoDono(Exception):
    def __init__(self) -> None:
        super().__init__(
            "Este é o último dono ativo: sem ele, ninguém mais cadastra usuários nem muda o "
            "estoque. Cadastre outro dono antes."
        )


def listar(db: Session) -> list[Usuario]:
    return list(db.scalars(select(Usuario).order_by(Usuario.nome, Usuario.id)))


def criar(db: Session, dados: UsuarioCadastro, origem: auditoria.Origem) -> Usuario:
    usuario = Usuario(
        nome=dados.nome,
        login=dados.login,
        papel=dados.papel,
        senha_hash=senha.gerar_hash(dados.senha),
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        # O login já vem em minúsculas: o UNIQUE do banco é a regra "sem diferenciar
        # maiúsculas", inclusive com dois cadastros ao mesmo tempo.
        raise LoginDuplicado from erro
    # Quem ganhou acesso, e com que papel. A senha inicial, nunca.
    auditoria.registrar(
        db,
        origem,
        "usuario.criado",
        "usuario",
        usuario.id,
        {"login": usuario.login, "nome": usuario.nome, "papel": usuario.papel},
    )
    db.commit()
    return usuario


def alterar(
    db: Session, usuario_id: int, dados: UsuarioAlteracao, origem: auditoria.Origem
) -> Usuario:
    usuario = _buscar(db, usuario_id)
    antes = _cadastro(usuario)
    papel = dados.papel if dados.papel is not None else usuario.papel
    ativo = dados.ativo if dados.ativo is not None else usuario.ativo
    if usuario.papel == "dono" and usuario.ativo and not (papel == "dono" and ativo):
        _garantir_outro_dono(db, usuario.id)
    if dados.nome is not None:
        usuario.nome = dados.nome
    usuario.papel, usuario.ativo = papel, ativo
    if not ativo:
        revogar_sessoes(db, usuario.id)
    # Virar dono, ser desativado: quem deu (ou tirou) o poder fica na trilha.
    if mudou := auditoria.diferencas(antes, _cadastro(usuario)):
        auditoria.registrar(
            db, origem, "usuario.alterado", "usuario", usuario.id, {"login": usuario.login, **mudou}
        )
    db.commit()
    return usuario


def redefinir_senha(
    db: Session, usuario_id: int, senha_nova: str, origem: auditoria.Origem
) -> None:
    """A senha esquecida ou vazada: o dono dá uma nova, e as sessões abertas caem (se
    vazou, o aparelho de quem a soube perde o acesso). Desfaz também o bloqueio."""
    usuario = _buscar(db, usuario_id)
    bloqueado = usuario.bloqueado_ate is not None and usuario.bloqueado_ate > agora()
    usuario.senha_hash = senha.gerar_hash(senha_nova)
    usuario.falhas_seguidas, usuario.bloqueado_ate = 0, None
    revogar_sessoes(db, usuario.id)
    # Quem redefine a senha de alguém pode entrar como ele: fica na trilha, sem a senha.
    auditoria.registrar(
        db,
        origem,
        "usuario.senha_redefinida",
        "usuario",
        usuario.id,
        {"login": usuario.login, "desbloqueou": bloqueado},
    )
    db.commit()


def _garantir_outro_dono(db: Session, usuario_id: int) -> None:
    # FOR UPDATE nos donos ativos: dois donos se desativando ao mesmo tempo passariam,
    # cada um vendo o outro, e a fazenda ficaria sem dono. Com a trava, o segundo espera o
    # primeiro e já o vê desativado. (O SQLite dos testes ignora a trava.)
    donos = db.scalars(
        select(Usuario.id).where(Usuario.papel == "dono", Usuario.ativo).with_for_update()
    ).all()
    if not set(donos) - {usuario_id}:
        raise UltimoDono


def _cadastro(usuario: Usuario) -> dict[str, object]:
    """O que se compara numa alteração: nunca a senha nem o hash dela."""
    return {"nome": usuario.nome, "papel": usuario.papel, "ativo": usuario.ativo}


def _buscar(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioInexistente
    return usuario
