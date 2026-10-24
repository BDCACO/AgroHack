"""Garante o papel da aplicação no PostgreSQL: o usuário com que a API conecta.

    python -m app.papel_da_aplicacao

O `POSTGRES_USER` do container oficial é superusuário e dono de tudo: a API conectada com
ele daria, a quem achasse uma falha nela, o cluster inteiro (DROP, ler os outros bancos,
`COPY ... PROGRAM` rodando comando no servidor). Por isso dois papéis:

- o **dono** (`MIGRATIONS_DATABASE_URL`), usado só pelo Alembic e por este comando;
- o **da aplicação** (`DATABASE_URL`), que não é superusuário, não é dono de nada, não cria
  nada: só `SELECT, INSERT, UPDATE, DELETE` nas tabelas e `USAGE, SELECT` nas sequências de
  `public`. Nada de `TRUNCATE`, `REFERENCES`, `TRIGGER`, `CREATE`, `ALTER`, `DROP`. Da
  `alembic_version`, só lê: quem anda o schema é o Alembic. Na trilha de auditoria
  (`eventos_de_auditoria`), só acrescenta e lê: nada de `UPDATE` nem `DELETE`.

Roda no entrypoint do container, como o dono, a cada subida, depois do `alembic upgrade
head`: cria o papel se não existe, acerta a senha e os atributos dele e refaz as
permissões. Idempotente, e funciona no banco novo e no que já tem dados (o volume de
quem já usava o projeto, onde os scripts de inicialização do PostgreSQL não rodam de
novo). O `ALTER DEFAULT PRIVILEGES` faz a tabela criada por uma migration futura nascer
com as mesmas permissões, mesmo que ela rode sem este comando depois (`make migrate`).

O nome e a senha do papel vêm da própria `DATABASE_URL` (montada pelo compose a partir de
`APP_DB_USER` e `APP_DB_PASSWORD`): uma fonte só, e o que a API usa é o que se garante.
"""

import re
import sys
from dataclasses import dataclass

import psycopg
from psycopg import sql
from sqlalchemy import URL, make_url

from app.core.config import Settings, get_settings

# Minúsculas, sem aspas: o nome aparece cru no `psql`, nos logs e no pg_hba.
PAPEL_VALIDO = re.compile(r"[a-z_][a-z0-9_]{0,62}")
# Vai numa URL de conexão: só letras e números, e comprida, já que é de máquina.
SENHA_VALIDA = re.compile(r"[A-Za-z0-9]{12,}")
# Duas subidas ao mesmo tempo (duas réplicas da API) não criam o papel duas vezes.
TRAVA = "campocerto: papel da aplicação"
# Onde a API só acrescenta e lê (INSERT e SELECT): a trilha de auditoria. Um rastro que a
# API pudesse alterar ou apagar não provaria nada a quem achasse uma falha nela. A
# migration 0012 já tira esses poderes ao criar a tabela; aqui eles saem de novo a cada
# subida, depois do GRANT em todas as tabelas, que os devolveria.
SOMENTE_ACRESCENTAR = ("eventos_de_auditoria",)


class ConfiguracaoInvalida(Exception):
    """A configuração não permite garantir o papel. A mensagem nunca leva a senha."""


@dataclass(frozen=True)
class Papeis:
    papel: str
    senha: str
    url_do_dono: URL


def ler_papeis(settings: Settings) -> Papeis | None:
    """O papel da aplicação e a conexão do dono, conferidos. None quando a API e as
    migrations usam o mesmo papel (o desenvolvimento com um papel só): mexer nas
    permissões do próprio dono o deixaria sem poder de DDL."""
    api = make_url(settings.database_url)
    dono = make_url(settings.url_das_migrations)
    if api.get_backend_name() != "postgresql" or dono.get_backend_name() != "postgresql":
        raise ConfiguracaoInvalida("o papel da aplicação só existe no PostgreSQL.")
    if api.username == dono.username:
        return None
    if api.username is None or not PAPEL_VALIDO.fullmatch(api.username):
        raise ConfiguracaoInvalida(
            "o usuário da DATABASE_URL (APP_DB_USER) tem de ser minúsculas, números e "
            "sublinhado, começando por letra, com até 63 caracteres."
        )
    if api.password is None or not SENHA_VALIDA.fullmatch(str(api.password)):
        raise ConfiguracaoInvalida(
            "a senha do papel da aplicação (APP_DB_PASSWORD) tem de ter só letras e números, "
            "pelo menos 12 (gere com: openssl rand -hex 16)."
        )
    if (api.host, api.port, api.database) != (dono.host, dono.port, dono.database):
        raise ConfiguracaoInvalida(
            "a DATABASE_URL e a MIGRATIONS_DATABASE_URL têm de apontar para o mesmo banco."
        )
    return Papeis(papel=api.username, senha=str(api.password), url_do_dono=dono)


def garantir(conexao: psycopg.Connection, papel: str, senha: str) -> None:
    """Cria ou acerta o papel e as permissões dele, numa transação só. `conexao` é a do
    dono do schema."""
    nome = sql.Identifier(papel)
    with conexao.transaction():
        conexao.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [TRAVA])
        dono, banco = conexao.execute("SELECT current_user, current_database()").fetchone()
        if conexao.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [papel]).fetchone() is None:
            conexao.execute(sql.SQL("CREATE ROLE {} LOGIN").format(nome))
        # A senha vai já cifrada (SCRAM, calculado aqui pela libpq): nem um log_statement
        # ligado no servidor veria a senha em claro.
        cifrada = conexao.pgconn.encrypt_password(senha.encode(), papel.encode(), b"scram-sha-256")
        # NOINHERIT: se alguém um dia puser o papel dentro de outro, ele não herda os
        # poderes de lá sem um SET ROLE explícito (e a API em produção nem sobe assim).
        conexao.execute(
            sql.SQL(
                "ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                " NOBYPASSRLS NOINHERIT PASSWORD {}"
            ).format(nome, sql.Literal(cifrada.decode()))
        )
        for comando in (
            "GRANT CONNECT ON DATABASE {banco} TO {papel}",
            "GRANT USAGE ON SCHEMA public TO {papel}",
            "REVOKE CREATE ON SCHEMA public FROM {papel}",
            # Do zero a cada subida: o que uma versão anterior tenha dado a mais sai.
            "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {papel}",
            "REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {papel}",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {papel}",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {papel}",
            # As tabelas que as migrations do dono criarem depois já nascem assim.
            "ALTER DEFAULT PRIVILEGES FOR ROLE {dono} IN SCHEMA public"
            " GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {papel}",
            "ALTER DEFAULT PRIVILEGES FOR ROLE {dono} IN SCHEMA public"
            " GRANT USAGE, SELECT ON SEQUENCES TO {papel}",
        ):
            conexao.execute(
                sql.SQL(comando).format(
                    banco=sql.Identifier(banco), papel=nome, dono=sql.Identifier(dono)
                )
            )
        if conexao.execute("SELECT to_regclass('public.alembic_version')").fetchone()[0]:
            conexao.execute(
                sql.SQL("REVOKE INSERT, UPDATE, DELETE ON public.alembic_version FROM {}").format(
                    nome
                )
            )
        for tabela in SOMENTE_ACRESCENTAR:
            # O GRANT acima, em todas as tabelas, devolveu o UPDATE e o DELETE: tira de novo.
            if conexao.execute("SELECT to_regclass(%s)", [f"public.{tabela}"]).fetchone()[0]:
                conexao.execute(
                    sql.SQL("REVOKE UPDATE, DELETE, TRUNCATE ON {} FROM {}").format(
                        sql.Identifier("public", tabela), nome
                    )
                )


def main() -> None:
    try:
        papeis = ler_papeis(get_settings())
    except ConfiguracaoInvalida as erro:
        sys.exit(f"Papel da aplicação: {erro}")
    if papeis is None:
        print("A API usa o mesmo papel das migrations: nenhum papel da aplicação a garantir.")
        return
    dono = papeis.url_do_dono
    try:
        with psycopg.connect(
            host=dono.host,
            port=dono.port or 5432,
            dbname=dono.database,
            user=dono.username,
            password=dono.password,
        ) as conexao:
            garantir(conexao, papeis.papel, papeis.senha)
    except psycopg.Error as erro:
        # Só a mensagem do servidor: nunca o comando, que leva a senha cifrada.
        sys.exit(
            f"Papel da aplicação: o PostgreSQL recusou ({erro.sqlstate}): "
            f"{erro.diag.message_primary}"
        )
    print(f"Papel da aplicação garantido: {papeis.papel} (só lê e grava dados).")


if __name__ == "__main__":
    main()
