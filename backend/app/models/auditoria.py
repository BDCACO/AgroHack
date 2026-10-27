"""A trilha de auditoria: o que de sensível ou destrutivo aconteceu, quem fez, quando e de
onde, com o conteúdo do que foi apagado.

Somente acrescentar. O papel da aplicação no PostgreSQL só faz INSERT e SELECT aqui
(app/papel_da_aplicacao.py), e a migration 0012 põe um gatilho que recusa UPDATE e DELETE
até para o dono: um rastro que quem apagou pode apagar não prova nada.

O evento é gravado na mesma transação da ação (app/services/auditoria.py): se a ação
falha, não há evento; se o evento falha, a ação não acontece.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.usuario import DataHora, Usuario

# JSONB no PostgreSQL (consultável, e sem o texto repetido a cada leitura); JSON no SQLite
# dos testes, que não conhece o outro.
Dados = JSON().with_variant(JSONB(), "postgresql")


class EventoDeAuditoria(Base):
    __tablename__ = "eventos_de_auditoria"
    __table_args__ = (
        CheckConstraint("origem IN ('api', 'terminal')", name="origem_valida"),
        # A consulta é sempre "os mais recentes primeiro" (ocorrido_em desc, id desc), com um
        # filtro opcional. Um índice por filtro, já nessa ordem: a página sai lendo só as
        # linhas dela. São poucas gravações (ações raras), e quatro índices custam pouco.
        Index("ix_eventos_de_auditoria_ocorrido_em_id", "ocorrido_em", "id"),
        Index("ix_eventos_de_auditoria_acao_ocorrido_em_id", "acao", "ocorrido_em", "id"),
        # Começa por usuario_id: serve também à FK.
        Index(
            "ix_eventos_de_auditoria_usuario_id_ocorrido_em_id", "usuario_id", "ocorrido_em", "id"
        ),
        # A história de uma coisa só ("o que aconteceu com o insumo 12").
        Index(
            "ix_eventos_de_auditoria_entidade_ocorrido_em_id",
            "entidade",
            "entidade_id",
            "ocorrido_em",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # O relógio do servidor, nunca o do pedido: quem fez não escolhe quando fez.
    ocorrido_em: Mapped[datetime] = mapped_column(
        DataHora, default=lambda: datetime.now(UTC), server_default=func.now()
    )
    # Quem fez. Vazio com a autenticação desligada, num comando do terminal e no login
    # recusado (quem tentou não é conhecido; o alvo vai em entidade_id). RESTRICT: usuário
    # não se apaga, desativa.
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="RESTRICT"))
    # Código estável ("movimentacao.removida"): a tela e os filtros dependem dele.
    acao: Mapped[str] = mapped_column(String(40))
    # Sobre o quê ("movimentacao", 7). Vazio no que não é de uma coisa só (a demonstração).
    entidade: Mapped[str | None] = mapped_column(String(20))
    entidade_id: Mapped[int | None]
    # O conteúdo do que foi apagado; numa alteração, o antes e o depois do que mudou; numa
    # importação, o resumo. Nunca senha, hash de senha nem token.
    dados: Mapped[dict[str, Any]] = mapped_column(Dados, default=dict)
    # De onde: a API ou um comando no servidor (a demonstração, o criar-dono).
    origem: Mapped[str] = mapped_column(String(8))
    # O endereço que o uvicorn viu: atrás de um proxy, o do proxy (ver docs/ARQUITETURA.md).
    ip: Mapped[str | None] = mapped_column(String(45))
    # O que o aparelho disse ser no login ("Celular do Zé"), copiado da sessão.
    dispositivo: Mapped[str | None] = mapped_column(String(120))

    usuario: Mapped[Usuario | None] = relationship(lazy="joined")

    @property
    def feito_por(self) -> str | None:
        """O nome de quem fez, como o `lancado_por` da movimentação."""
        return None if self.usuario is None else self.usuario.nome
