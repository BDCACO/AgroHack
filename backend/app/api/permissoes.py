"""Quem pode o quê: as dependências que cada grupo de rotas exige, aplicadas no
`include_router` (app/api/router.py), e não rota a rota, para nenhuma nascer aberta por
esquecimento. `tests/test_permissoes.py` percorre todas as rotas do app e confere que cada
uma está num nível.

Com a autenticação desligada (AUTENTICACAO=false, o padrão fora de produção), pedido sem
token passa como antes, com os poderes do dono. Mas quem manda token é reconhecido e tem
o papel dele: token inválido é 401 e funcionário em rota do dono é 403, ligada ou não.
Assim o site e o app já implementam o login contra a API de desenvolvimento.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Sessao, Usuario
from app.services import autenticacao

# auto_error=False: a falta do token é decidida aqui (pode ser permitida), não pelo FastAPI.
_bearer = HTTPBearer(auto_error=False, description="O token devolvido por POST /auth/entrar.")


def sessao_atual(
    credencial: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Sessao | None:
    """A sessão do token, se veio um. Token que não abre sessão é 401 sempre: quem manda
    token quer ser reconhecido, e seguir como anônimo esconderia o erro."""
    if credencial is None:
        return None
    try:
        return autenticacao.sessao_do_token(db, credencial.credentials)
    except autenticacao.SessaoInvalida as erro:
        raise _nao_autenticado(str(erro)) from None


def usuario_atual(sessao: Sessao | None = Depends(sessao_atual)) -> Usuario | None:
    """Quem fez o pedido (para a auditoria), ou None sem login."""
    return None if sessao is None else sessao.usuario


def exigir_sessao(sessao: Sessao | None = Depends(sessao_atual)) -> Sessao:
    """Rotas da própria sessão (/auth/eu, sair, trocar a senha): sem login não há de quem
    falar, nem com a autenticação desligada."""
    if sessao is None:
        raise _nao_autenticado(_FALTA_O_LOGIN)
    return sessao


def _nao_autenticado(frase: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, frase, headers={"WWW-Authenticate": "Bearer"}
    )


_FALTA_O_LOGIN = "Entre com o seu login e senha para continuar."
