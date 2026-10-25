"""Quem usa o CampoCerto (o dono e os funcionários) e as sessões abertas por eles.

Usuário não se apaga, desativa: as movimentações dizem quem as lançou, e esse registro
não pode sumir nem apontar para ninguém.
"""

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, TypeDecorator, func, true
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class DataHora(TypeDecorator[datetime]):
    """Data e hora sempre com fuso (UTC). O PostgreSQL devolve com fuso; o SQLite dos
    testes, sem, e comparar as duas coisas é erro no Python."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_result_value(self, valor: datetime | None, dialect: Dialect) -> datetime | None:
        if valor is not None and valor.tzinfo is None:
            return valor.replace(tzinfo=UTC)
        return valor


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("papel IN ('dono', 'funcionario')", name="papel_valido"),
        # O login se compara sem diferenciar maiúsculas: guardado já em minúsculas, o
        # UNIQUE simples basta, e vale também para o que for inserido fora da API.
        CheckConstraint("login = lower(login)", name="login_minusculo"),
        CheckConstraint("falhas_seguidas >= 0", name="falhas_nao_negativas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    login: Mapped[str] = mapped_column(String(40), unique=True)
    # scrypt$n$r$p$sal$hash (app/core/senha.py): nunca a senha.
    senha_hash: Mapped[str] = mapped_column(String(255))
    papel: Mapped[str] = mapped_column(String(11))
    ativo: Mapped[bool] = mapped_column(default=True, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(
        DataHora, default=lambda: datetime.now(UTC), server_default=func.now()
    )
    # Contra adivinhação de senha: erros seguidos no login e até quando ele fica
    # bloqueado. No banco, e não na memória do processo: sobrevive a reiniciar a API.
    falhas_seguidas: Mapped[int] = mapped_column(default=0, server_default="0")
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DataHora)


class Sessao(Base):
    """Um login aberto num aparelho. O token não fica aqui, só o SHA-256 dele: quem lê o
    banco não consegue se passar por ninguém."""

    __tablename__ = "sessoes"
    __table_args__ = (CheckConstraint("expira_em > criada_em", name="expira_depois_de_criada"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT, como o usuário da movimentação: usuário não se apaga.
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="RESTRICT"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    criada_em: Mapped[datetime] = mapped_column(DataHora)
    expira_em: Mapped[datetime] = mapped_column(DataHora)
    # Sair, trocar a senha, ser desativado ou o encerramento pela lista de sessões
    # (o celular perdido) encerram a sessão antes de expirar.
    revogada_em: Mapped[datetime | None] = mapped_column(DataHora)
    # O que o aparelho disse ser ("Celular do Zé"), para o dono saber onde há login aberto.
    dispositivo: Mapped[str | None] = mapped_column(String(120))
    # Quando a sessão foi usada pela última vez, anotado de tempos em tempos e não a cada
    # pedido (app/services/autenticacao.py): mostra qual aparelho está em uso e renova a
    # validade de quem usa.
    ultimo_uso_em: Mapped[datetime] = mapped_column(DataHora)
    # O IP do login, pelo critério da auditoria (o que o servidor viu, nunca o
    # X-Forwarded-For). Vazio nas sessões abertas antes de existir a coluna.
    ip: Mapped[str | None] = mapped_column(String(45))

    usuario: Mapped[Usuario] = relationship(lazy="joined")
