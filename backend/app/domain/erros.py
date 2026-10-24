"""Erros de regra de negócio.

O domínio levanta um CÓDIGO estável e uma mensagem para o usuário; quem
traduz para HTTP é `app/api/erros.py`. Assim o domínio não conhece FastAPI.
"""


class ErroDeNegocio(Exception):
    codigo = "ERRO_DE_NEGOCIO"

    def __init__(self, mensagem: str) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem


class InsumoNaoEncontrado(ErroDeNegocio):
    codigo = "INSUMO_NAO_ENCONTRADO"

    def __init__(self) -> None:
        super().__init__("Insumo não encontrado.")


class InsumoDuplicado(ErroDeNegocio):
    codigo = "INSUMO_DUPLICADO"

    def __init__(self, nome: str) -> None:
        super().__init__(f"Já existe um insumo chamado “{nome}”.")


class InsumoComMovimentacoes(ErroDeNegocio):
    codigo = "INSUMO_COM_MOVIMENTACOES"

    def __init__(self) -> None:
        super().__init__(
            "Este insumo tem movimentações registradas. Remova as movimentações antes."
        )


class MovimentacaoNaoEncontrada(ErroDeNegocio):
    codigo = "MOVIMENTACAO_NAO_ENCONTRADA"

    def __init__(self) -> None:
        super().__init__("Movimentação não encontrada.")


class EstoqueInsuficiente(ErroDeNegocio):
    codigo = "ESTOQUE_INSUFICIENTE"
