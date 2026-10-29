"""Login, sessão e troca de senha.

O token é opaco (`secrets.token_urlsafe`), e não um JWT: o servidor o procura no banco a
cada pedido, então sair, trocar a senha e desativar alguém valem na hora, sem lista de
revogação à parte. No banco fica só o SHA-256 dele; o próprio token sai uma vez, na
resposta do login. SHA-256 simples, sem sal nem Argon2id, basta: são 256 bits aleatórios,
ninguém os adivinha, e a conferência de cada pedido precisa ser rápida.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import cache

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.core import senha
from app.core.relogio import agora
from app.models import Sessao, Usuario
from app.services import auditoria

# 30 dias sem uso, e não horas: o app fica dias no campo sem sinal, lançando na fila, e
# um login vencido no meio da lida obrigaria o funcionário a achar sinal e lembrar a senha
# só para continuar. Renova a cada uso (validade deslizante): quem usa todo dia não é
# derrubado no 30º, e o que vence é a sessão esquecida, do aparelho que ninguém mais abre.
# O risco do prazo longo (celular perdido) se resolve encerrando aquela sessão pela lista
# de sessões, sem derrubar os outros aparelhos (app/services/sessoes.py).
VALIDADE_DA_SESSAO = timedelta(days=30)
# O teto, desde o login, mesmo com uso: um token copiado (de um backup do celular, de um
# computador emprestado) não vive para sempre só porque alguém o usa, e a senha é pedida
# de novo de tempos em tempos, o que também a mantém na memória de quem a usa. 90 dias é
# um login a cada três meses: pouco incômodo, e o app avisa antes (expira_em na lista).
TETO_DA_SESSAO = timedelta(days=90)
# O último uso é anotado no banco no máximo a cada 5 minutos, e não a cada pedido. O
# Painel abre vários pedidos de uma vez e recarrega tudo a cada lançamento: gravar em cada
# um seria um UPDATE (e o WAL dele) por leitura, e os pedidos paralelos do mesmo token
# esperariam um pelo outro na trava da linha. 5 minutos ainda respondem "está em uso
# agora?", que é o que o dono pergunta ao procurar o celular perdido, e somem diante dos
# 30 dias da validade: renovar com até 5 minutos de atraso não muda nada para ninguém. No
# pior caso, um aparelho usado sem parar grava 12 vezes por hora.
ANOTAR_O_USO_A_CADA = timedelta(minutes=5)
# Contra quem tenta adivinhar a senha: 5 erros seguidos bloqueiam o login por 15 minutos.
# Quem errou digitando tem folga; quem testa senhas faz 20 por hora, e não milhares. Por
# usuário, no banco: vale para todos os processos da API e sobrevive a reiniciar.
TENTATIVAS_ANTES_DO_BLOQUEIO = 5
TEMPO_DE_BLOQUEIO = timedelta(minutes=15)

# A mesma frase para login inexistente, senha errada, usuário desativado e login
# bloqueado: nenhuma resposta conta a quem tenta adivinhar que o login existe. Por isso a
# regra do bloqueio vai na própria frase, para quem errou de verdade saber esperar.
_LOGIN_RECUSADO = (
    "Login ou senha incorretos. Depois de 5 tentativas erradas seguidas, o login fica "
    "bloqueado por 15 minutos."
)


class LoginRecusado(Exception):
    def __init__(self) -> None:
        super().__init__(_LOGIN_RECUSADO)


class SessaoInvalida(Exception):
    """O token não abre sessão: a frase diz o porquê, para a tela pedir o login de novo."""


class SenhaAtualIncorreta(Exception):
    pass


class SenhaAtualFaltando(Exception):
    pass


class LoginEmUso(Exception):
    pass


def normalizar_login(login: str) -> str:
    """O login se compara sem diferenciar maiúsculas nem espaços nas pontas."""
    return login.strip().lower()


def entrar(
    db: Session, login: str, senha_digitada: str, dispositivo: str | None, ip: str | None
) -> tuple[str, Sessao]:
    """Confere login e senha e abre uma sessão. Devolve o token (a única vez em que ele
    existe fora do aparelho) e a sessão. A recusa de um login que existe vai para a trilha
    de auditoria, com o IP e o aparelho que o pedido disse ser."""
    origem = auditoria.Origem(ip=ip, dispositivo=dispositivo)
    login = normalizar_login(login)
    # O PostgreSQL não aceita caractere nulo num texto: a busca daria erro, e não a
    # resposta do login que não existe. Nenhum login cadastrado tem um.
    # FOR UPDATE: as tentativas no mesmo login entram uma de cada vez, e cinco senhas
    # mandadas ao mesmo tempo não passam todas antes de a primeira contar o erro.
    usuario = None
    if "\x00" not in login:
        usuario = db.scalar(select(Usuario).where(Usuario.login == login).with_for_update())
    if usuario is None:
        # O mesmo hash lento de um login que existe: sem ele, a resposta rápida denunciaria
        # quais logins existem. Sem evento: não há a quem atribuir, e o que se digitou no
        # campo do login pode ser a senha.
        senha.conferir(senha_digitada, _hash_de_mentira())
        raise LoginRecusado
    if not _conferir_contando_erros(db, usuario, senha_digitada, origem):
        db.commit()
        raise LoginRecusado
    if not usuario.ativo:
        registrar_recusa(db, origem, usuario, "usuario_desativado")
        db.commit()
        raise LoginRecusado
    if senha.precisa_refazer(usuario.senha_hash):
        # O custo do hash subiu desde que esta senha foi gravada: aproveita que ela chegou.
        usuario.senha_hash = senha.gerar_hash(senha_digitada)
    return abrir_sessao(db, usuario, dispositivo, ip)


def abrir_sessao(
    db: Session, usuario: Usuario, dispositivo: str | None, ip: str | None = None
) -> tuple[str, Sessao]:
    token = secrets.token_urlsafe(32)
    momento = agora()
    sessao = Sessao(
        usuario=usuario,
        token_hash=_hash_do_token(token),
        criada_em=momento,
        expira_em=momento + VALIDADE_DA_SESSAO,
        ultimo_uso_em=momento,
        dispositivo=dispositivo,
        ip=ip,
    )
    db.add(sessao)
    db.commit()
    return token, sessao


def sessao_do_token(db: Session, token: str) -> Sessao:
    """A sessão que o token abre, conferida a cada pedido: existe, não foi encerrada, não
    expirou e o usuário continua ativo. Anota o uso e renova a validade de tempos em
    tempos (`ANOTAR_O_USO_A_CADA`)."""
    momento = agora()
    sessao = db.scalar(select(Sessao).where(Sessao.token_hash == _hash_do_token(token)))
    if sessao is None:
        raise SessaoInvalida("Sessão inválida: entre de novo com o seu login e senha.")
    if sessao.revogada_em is not None:
        raise SessaoInvalida("Sessão encerrada: entre de novo com o seu login e senha.")
    if sessao.expira_em <= momento:
        raise SessaoInvalida("A sessão expirou: entre de novo com o seu login e senha.")
    if not sessao.usuario.ativo:
        raise SessaoInvalida("Usuário desativado: fale com o dono da fazenda.")
    if momento - sessao.ultimo_uso_em >= ANOTAR_O_USO_A_CADA:
        _anotar_o_uso(db, sessao, momento)
    return sessao


def validade_renovada(sessao: Sessao, momento: datetime) -> datetime:
    """Até quando a sessão vale, usada em `momento`: 30 dias a partir do uso, nunca além
    de 90 dias desde o login."""
    return min(momento + VALIDADE_DA_SESSAO, sessao.criada_em + TETO_DA_SESSAO)


def _anotar_o_uso(db: Session, sessao: Sessao, momento: datetime) -> None:
    """Grava o último uso e a validade renovada, e faz o commit na hora, antes de a rota
    começar. Assim a trava da linha da sessão dura milissegundos: segurada até o fim do
    pedido (um relatório de segundos), os outros pedidos do mesmo aparelho esperariam por
    ela e cairiam no lock_timeout; e a transação não fica aberta além do que a rota já
    abriria. A condição repetida no UPDATE resolve a corrida entre dois pedidos que viram
    o uso velho ao mesmo tempo: o segundo espera o primeiro e não acha mais o que gravar.
    Nem ressuscita a sessão encerrada nesse meio-tempo."""
    expira_em = validade_renovada(sessao, momento)
    resultado = db.execute(
        update(Sessao)
        .where(
            Sessao.id == sessao.id,
            Sessao.revogada_em.is_(None),
            Sessao.ultimo_uso_em <= momento - ANOTAR_O_USO_A_CADA,
        )
        .values(ultimo_uso_em=momento, expira_em=expira_em)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    if resultado.rowcount:
        # O objeto acompanha o banco sem outra consulta e sem virar alteração pendente.
        set_committed_value(sessao, "ultimo_uso_em", momento)
        set_committed_value(sessao, "expira_em", expira_em)


def sair(db: Session, sessao: Sessao) -> None:
    sessao.revogada_em = agora()
    db.commit()


def trocar_senha(
    db: Session, sessao: Sessao, senha_atual: str, senha_nova: str, origem: auditoria.Origem
) -> None:
    """Troca a senha e encerra as outras sessões do usuário: se a troca é porque alguém
    soube a senha, o aparelho dele perde o acesso. A sessão de quem trocou continua."""
    usuario = sessao.usuario
    db.refresh(usuario, with_for_update=True)
    # Conta como tentativa de login: quem pegou o celular com a sessão aberta não pode
    # testar senhas por aqui sem limite.
    if not _conferir_contando_erros(db, usuario, senha_atual, origem, "senha_atual_incorreta"):
        db.commit()
        raise SenhaAtualIncorreta
    usuario.senha_hash = senha.gerar_hash(senha_nova)
    revogar_sessoes(db, usuario.id, exceto=sessao.id)
    # A sessão roubada que troca a senha tranca o dono fora: fica na trilha.
    auditoria.registrar(
        db, origem, "usuario.senha_trocada", "usuario", usuario.id, {"login": usuario.login}
    )
    db.commit()


def alterar_perfil(
    db: Session,
    sessao: Sessao,
    nome: str | None,
    login: str | None,
    senha_atual: str | None,
    origem: auditoria.Origem,
) -> Usuario:
    """O próprio nome e o próprio login. O login novo pede a senha atual, contada como
    tentativa de login (quem pegou o celular com a sessão aberta não testa senhas por aqui
    sem limite). As sessões continuam: o token não depende do login."""
    usuario = sessao.usuario
    db.refresh(usuario, with_for_update=True)
    antes = {"nome": usuario.nome, "login": usuario.login}
    if login is not None and login != usuario.login:
        if senha_atual is None:
            db.rollback()
            raise SenhaAtualFaltando
        if not _conferir_contando_erros(db, usuario, senha_atual, origem, "senha_atual_incorreta"):
            db.commit()
            raise SenhaAtualIncorreta
        usuario.login = login
    if nome is not None:
        usuario.nome = nome
    try:
        db.flush()
    except IntegrityError as erro:
        db.rollback()
        raise LoginEmUso from erro
    # O login trocado é o mesmo que "outra pessoa entra agora com outro nome": fica na trilha.
    depois = {"nome": usuario.nome, "login": usuario.login}
    if mudou := auditoria.diferencas(antes, depois):
        auditoria.registrar(
            db, origem, "usuario.alterado", "usuario", usuario.id, {"login": usuario.login, **mudou}
        )
    db.commit()
    return usuario


def revogar_sessoes(db: Session, usuario_id: int, exceto: int | None = None) -> None:
    """Encerra as sessões abertas do usuário (sem commit: vai junto com a mudança que pede)."""
    consulta = update(Sessao).where(Sessao.usuario_id == usuario_id, Sessao.revogada_em.is_(None))
    if exceto is not None:
        consulta = consulta.where(Sessao.id != exceto)
    db.execute(consulta.values(revogada_em=agora()))


def _conferir_contando_erros(
    db: Session,
    usuario: Usuario,
    senha_digitada: str,
    origem: auditoria.Origem,
    motivo_do_erro: str = "senha_incorreta",
) -> bool:
    """Confere a senha respeitando o bloqueio: o erro conta, o acerto zera, e bloqueado
    nada confere (nem a senha certa). A recusa e o bloqueio vão para a trilha de auditoria
    junto com a contagem, na mesma transação. Não grava: quem chama faz o commit."""
    momento = agora()
    # Sempre o hash lento, mesmo bloqueado: o tempo da resposta não denuncia o bloqueio.
    confere = senha.conferir(senha_digitada, usuario.senha_hash)
    if usuario.bloqueado_ate is not None and usuario.bloqueado_ate > momento:
        # Sem contar o erro nem estender o prazo: senão, quem tenta sem parar empurraria o
        # fim do bloqueio para sempre, e o funcionário nunca mais entraria.
        registrar_recusa(db, origem, usuario, "bloqueado")
        return False
    if confere:
        usuario.falhas_seguidas, usuario.bloqueado_ate = 0, None
        return True
    registrar_recusa(db, origem, usuario, motivo_do_erro)
    usuario.falhas_seguidas += 1
    if usuario.falhas_seguidas >= TENTATIVAS_ANTES_DO_BLOQUEIO:
        # Zera a conta: passado o bloqueio, são mais 5 tentativas, e não uma.
        usuario.falhas_seguidas, usuario.bloqueado_ate = 0, momento + TEMPO_DE_BLOQUEIO
        auditoria.registrar(
            db,
            origem,
            "login.bloqueado",
            "usuario",
            usuario.id,
            {
                "login": usuario.login,
                "tentativas": TENTATIVAS_ANTES_DO_BLOQUEIO,
                "bloqueado_ate": usuario.bloqueado_ate,
            },
        )
    return False


def registrar_recusa(db: Session, origem: auditoria.Origem, usuario: Usuario, motivo: str) -> None:
    """O login recusado de um usuário que existe. Quem tentou não é conhecido (no login,
    `origem` não tem usuário); o alvo vai em `entidade_id`, e o motivo, que a resposta não
    conta a quem tentou, fica para o dono."""
    auditoria.registrar(
        db,
        origem,
        "login.recusado",
        "usuario",
        usuario.id,
        {"login": usuario.login, "motivo": motivo},
    )


def _hash_do_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@cache
def _hash_de_mentira() -> str:
    return senha.gerar_hash(secrets.token_urlsafe(16))
