"""As sessões abertas de cada um: a lista e o encerramento de um aparelho só.

O caso que motiva: o funcionário perdeu o celular com o app logado. Antes, só desativar o
usuário ou redefinir a senha dele derrubavam aquela sessão, e com ela todos os outros
aparelhos. Agora encerra-se só a do celular: ele mesmo, de outro aparelho, ou o dono,
pela gestão de usuários.

Encerrar a sessão que faz o pedido é sair, e não entra na trilha (como o `POST
/auth/sair`). Encerrar qualquer outra entra (`sessao.encerrada`, `sessao.encerradas`):
o dono derrubando o aparelho de alguém, ou alguém derrubando os próprios aparelhos, que
pode ser quem pegou a sessão de outro e quer o dono dela fora.
"""

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.relogio import agora
from app.models import Sessao, Usuario
from app.services import auditoria
from app.services.usuarios import UsuarioInexistente


class SessaoInexistente(Exception):
    """Não há sessão ativa com esse id para esse usuário. A mesma resposta para a que não
    existe, a já encerrada ou vencida e a de outro usuário: o id não conta nada."""


def ativas(db: Session, usuario_id: int) -> list[Sessao]:
    """As sessões que ainda abrem a API (nem encerradas nem vencidas), a usada por último
    primeiro."""
    return list(
        db.scalars(
            _ativas_do_usuario(usuario_id).order_by(Sessao.ultimo_uso_em.desc(), Sessao.id.desc())
        )
    )


def encerrar(
    db: Session,
    usuario_id: int,
    sessao_id: int,
    atual_id: int | None,
    origem: auditoria.Origem,
) -> None:
    """Encerra uma sessão ativa do usuário. `atual_id` é a sessão que faz o pedido:
    encerrá-la é sair, sem evento; qualquer outra vai para a trilha."""
    # FOR UPDATE: dois pedidos encerrando a mesma sessão não deixam dois eventos; o segundo
    # espera o primeiro e já não a acha ativa (404). Só a linha da sessão (OF), e não a do
    # usuário, que vem junto pelo JOIN.
    sessao = db.scalar(
        _ativas_do_usuario(usuario_id).where(Sessao.id == sessao_id).with_for_update(of=Sessao)
    )
    if sessao is None:
        raise SessaoInexistente
    sessao.revogada_em = agora()
    if sessao.id != atual_id:
        auditoria.registrar(
            db,
            origem,
            "sessao.encerrada",
            "usuario",
            usuario_id,
            {"login": sessao.usuario.login, "sessao": _retrato(sessao)},
        )
    db.commit()


def encerrar_todas(
    db: Session, usuario_id: int, exceto: int | None, origem: auditoria.Origem
) -> int:
    """Encerra as sessões ativas do usuário, menos `exceto` (a que faz o pedido), e diz
    quantas. Nenhuma a encerrar, nada na trilha."""
    usuario = _garantir_usuario(db, usuario_id)
    consulta = _ativas_do_usuario(usuario_id).order_by(Sessao.id).with_for_update(of=Sessao)
    if exceto is not None:
        consulta = consulta.where(Sessao.id != exceto)
    encerradas = list(db.scalars(consulta))
    momento = agora()
    for sessao in encerradas:
        sessao.revogada_em = momento
    if encerradas:
        auditoria.registrar(
            db,
            origem,
            "sessao.encerradas",
            "usuario",
            usuario_id,
            {"login": usuario.login, "sessoes": [_retrato(s) for s in encerradas]},
        )
    db.commit()
    return len(encerradas)


def _ativas_do_usuario(usuario_id: int) -> Select[tuple[Sessao]]:
    return select(Sessao).where(
        Sessao.usuario_id == usuario_id,
        Sessao.revogada_em.is_(None),
        Sessao.expira_em > agora(),
    )


def _garantir_usuario(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise UsuarioInexistente
    return usuario


def _retrato(sessao: Sessao) -> dict[str, Any]:
    """O que a trilha guarda da sessão encerrada: o bastante para o dono reconhecer o
    aparelho. Montado campo a campo: nunca o hash do token."""
    return {
        "id": sessao.id,
        "dispositivo": sessao.dispositivo,
        "ip": sessao.ip,
        "criada_em": sessao.criada_em,
        "ultimo_uso_em": sessao.ultimo_uso_em,
    }
