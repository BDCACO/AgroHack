from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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
