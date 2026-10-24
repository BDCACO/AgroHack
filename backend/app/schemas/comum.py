from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, StringConstraints

# Quantidade com até 3 casas (gramas de um kg, mililitros de um litro). Sai no
# JSON como número, não como string — o padrão do Pydantic para Decimal é
# string, o que obrigaria o front a converter em todo lugar.
Quantidade = Annotated[
    Decimal,
    Field(max_digits=14, decimal_places=3),
    PlainSerializer(float, return_type=float, when_used="json"),
]


def texto(max_length: int) -> StringConstraints:
    """Restrição de texto: aparado nas pontas, não vazio, com tamanho máximo.

    Uso: `nome: Annotated[str, texto(120)]`.
    """
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


class Erro(BaseModel):
    """Corpo de toda resposta de erro de regra de negócio."""

    codigo: str
    mensagem: str
