"""Login, sessão e troca de senha.

O token é opaco (`secrets.token_urlsafe`), e não um JWT: o servidor o procura no banco a
cada pedido, então sair, trocar a senha e desativar alguém valem na hora, sem lista de
revogação à parte. No banco fica só o SHA-256 dele; o próprio token sai uma vez, na
resposta do login. SHA-256 simples, sem sal nem scrypt, basta: são 256 bits aleatórios,
ninguém os adivinha, e a conferência de cada pedido precisa ser rápida.
"""

import hashlib
import secrets
from datetime import timedelta
from functools import cache

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import senha
from app.core.relogio import agora
from app.models import Sessao, Usuario

# 30 dias, e não horas: o app fica dias no campo sem sinal, lançando na fila, e um login
# vencido no meio da lida obrigaria o funcionário a achar sinal e lembrar a senha só para
# continuar. O risco do prazo longo (celular perdido) se resolve pelo dono, que desativa o
# usuário ou redefine a senha, e as sessões dele caem na hora.
VALIDADE_DA_SESSAO = timedelta(days=30)

_LOGIN_RECUSADO = "Login ou senha incorretos."


class LoginRecusado(Exception):
    def __init__(self) -> None:
        super().__init__(_LOGIN_RECUSADO)


class SessaoInvalida(Exception):
    """O token não abre sessão: a frase diz o porquê, para a tela pedir o login de novo."""


class SenhaAtualIncorreta(Exception):
    pass


def normalizar_login(login: str) -> str:
    """O login se compara sem diferenciar maiúsculas nem espaços nas pontas."""
    return login.strip().lower()


def entrar(
    db: Session, login: str, senha_digitada: str, dispositivo: str | None
) -> tuple[str, Sessao]:
    """Confere login e senha e abre uma sessão. Devolve o token (a única vez em que ele
    existe fora do aparelho) e a sessão."""
    usuario = db.scalar(select(Usuario).where(Usuario.login == normalizar_login(login)))
    if usuario is None:
        # O mesmo scrypt de um login que existe: sem ele, a resposta rápida denunciaria
        # quais logins existem.
        senha.conferir(senha_digitada, _hash_de_mentira())
        raise LoginRecusado
    if not senha.conferir(senha_digitada, usuario.senha_hash) or not usuario.ativo:
        raise LoginRecusado
    if senha.precisa_refazer(usuario.senha_hash):
        # O custo do hash subiu desde que esta senha foi gravada: aproveita que ela chegou.
        usuario.senha_hash = senha.gerar_hash(senha_digitada)
    return abrir_sessao(db, usuario, dispositivo)


def abrir_sessao(db: Session, usuario: Usuario, dispositivo: str | None) -> tuple[str, Sessao]:
    token = secrets.token_urlsafe(32)
    momento = agora()
    sessao = Sessao(
        usuario=usuario,
        token_hash=_hash_do_token(token),
        criada_em=momento,
        expira_em=momento + VALIDADE_DA_SESSAO,
        dispositivo=dispositivo,
    )
    db.add(sessao)
    db.commit()
    return token, sessao


def sessao_do_token(db: Session, token: str) -> Sessao:
    """A sessão que o token abre, conferida a cada pedido: existe, não foi encerrada, não
    expirou e o usuário continua ativo."""
    sessao = db.scalar(select(Sessao).where(Sessao.token_hash == _hash_do_token(token)))
    if sessao is None:
        raise SessaoInvalida("Sessão inválida: entre de novo com o seu login e senha.")
    if sessao.revogada_em is not None:
        raise SessaoInvalida("Sessão encerrada: entre de novo com o seu login e senha.")
    if sessao.expira_em <= agora():
        raise SessaoInvalida("A sessão expirou: entre de novo com o seu login e senha.")
    if not sessao.usuario.ativo:
        raise SessaoInvalida("Usuário desativado: fale com o dono da fazenda.")
    return sessao


def sair(db: Session, sessao: Sessao) -> None:
    sessao.revogada_em = agora()
    db.commit()


def trocar_senha(db: Session, sessao: Sessao, senha_atual: str, senha_nova: str) -> None:
    """Troca a senha e encerra as outras sessões do usuário: se a troca é porque alguém
    soube a senha, o aparelho dele perde o acesso. A sessão de quem trocou continua."""
    usuario = sessao.usuario
    if not senha.conferir(senha_atual, usuario.senha_hash):
        raise SenhaAtualIncorreta
    usuario.senha_hash = senha.gerar_hash(senha_nova)
    revogar_sessoes(db, usuario.id, exceto=sessao.id)
    db.commit()


def revogar_sessoes(db: Session, usuario_id: int, exceto: int | None = None) -> None:
    """Encerra as sessões abertas do usuário (sem commit: vai junto com a mudança que pede)."""
    consulta = update(Sessao).where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
    if exceto is not None:
        consulta = consulta.where(Sessao.id != exceto)
    db.execute(consulta.values(revogada_em=agora()))


def _hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@cache
def _hash_de_mentira() -> str:
    return senha.gerar_hash(secrets.token_urlsafe(16))
