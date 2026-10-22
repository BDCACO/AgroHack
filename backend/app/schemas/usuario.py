from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.estoque import SEM_CARACTERE_DE_CONTROLE

# Menos que isto, uma senha cai em minutos para quem tenta todas.
SENHA_MINIMA = 8
# Teto só contra pedido absurdo: o scrypt aceita senha longa sem problema.
SENHA_MAXIMA = 200

Papel = Literal["dono", "funcionario"]


class PedidoDeEntrada(BaseModel):
    # Sem aparar espaços aqui: na senha, o espaço faz parte dela (o login é aparado e posto
    # em minúsculas no serviço). E sem o formato do cadastro no login, de propósito: login
    # fora do formato é só um login que não existe, e a resposta tem de ser a mesma.
    login: str = Field(min_length=1, max_length=SENHA_MAXIMA)
    senha: str = Field(min_length=1, max_length=SENHA_MAXIMA)
    # O que o aparelho diz ser ("Celular do Zé"): o dono vê onde há login aberto.
    dispositivo: str | None = Field(default=None, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)


class UsuarioResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    login: str
    papel: Papel


class Entrada(BaseModel):
    # Devolvido uma vez só: o servidor guarda apenas o hash e não tem como mostrá-lo de novo.
    token: str
    expira_em: datetime
    usuario: UsuarioResumo


class TrocaDeSenha(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=SENHA_MAXIMA)
    senha_nova: str = Field(min_length=SENHA_MINIMA, max_length=SENHA_MAXIMA)


class UsuarioCadastro(BaseModel):
    nome: str = Field(min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE)
    # Só letras sem acento, números, ponto, hífen e sublinhado: "zé" digitado num teclado
    # sem acento seria outro login, e o funcionário não entraria.
    login: str = Field(pattern=r"^[a-z0-9._-]{2,40}$")
    senha: str = Field(min_length=SENHA_MINIMA, max_length=SENHA_MAXIMA)
    papel: Papel

    @field_validator("nome")
    @classmethod
    def _nome_aparado(cls, nome: str) -> str:
        if not nome.strip():
            raise ValueError("o nome não pode ficar em branco")
        return nome.strip()

    @field_validator("login", mode="before")
    @classmethod
    def _login_normalizado(cls, login: object) -> object:
        # Como o login compara: sem espaços nas pontas e em minúsculas.
        return login.strip().lower() if isinstance(login, str) else login


class UsuarioAlteracao(BaseModel):
    """O que vier muda; o que não vier fica como está."""

    nome: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=SEM_CARACTERE_DE_CONTROLE
    )
    papel: Papel | None = None
    # Desativar, e não apagar: as movimentações dizem quem as lançou.
    ativo: bool | None = None


class RedefinicaoDeSenha(BaseModel):
    senha_nova: str = Field(min_length=SENHA_MINIMA, max_length=SENHA_MAXIMA)


class UsuarioResposta(UsuarioResumo):
    ativo: bool
    criado_em: datetime
    # Até quando o login está bloqueado por senhas erradas seguidas (None: não está).
    bloqueado_ate: datetime | None
