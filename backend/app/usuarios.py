"""O primeiro dono, criado no servidor, e não pela rede:

    python -m app.usuarios criar-dono --login maria --nome "Dona Maria"

A senha é pedida no terminal (duas vezes, sem aparecer) ou, para automação, lida da
variável de ambiente SENHA_DO_DONO. Nunca por argumento: ficaria no histórico do shell e
na lista de processos. Não existe endpoint de "primeiro acesso": aberto na rede, quem
chegasse antes do dono viraria o dono.

Com um dono ativo, o comando se recusa (os próximos usuários o dono cria em
POST /usuarios), a não ser com `--outro-dono`: é a saída para quem tem o servidor e
perdeu o acesso do dono.
"""

import argparse
import getpass
import os
import sys

from pydantic import ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.database import get_sessionmaker
from app.models import Usuario
from app.schemas.usuario import SENHA_MINIMA, UsuarioCadastro
from app.services import auditoria, usuarios

# Lida aqui, e não em core/config.py: é entrada deste comando, não configuração da API.
VARIAVEL_DA_SENHA = "SENHA_DO_DONO"


class JaHaDono(Exception):
    pass


def criar_dono(db: Session, login: str, nome: str, senha: str, *, outro_dono: bool) -> Usuario:
    """Valida como o cadastro da API (UsuarioCadastro) e cria o dono."""
    dados = UsuarioCadastro(login=login, nome=nome, senha=senha, papel="dono")
    dono_ativo = exists().where(Usuario.papel == "dono", Usuario.ativo)
    if not outro_dono and db.scalar(select(dono_ativo)):
        raise JaHaDono
    return usuarios.criar(db, dados, auditoria.TERMINAL)


def main(argumentos: list[str] | None = None) -> None:
    leitor = argparse.ArgumentParser(prog="python -m app.usuarios")
    acoes = leitor.add_subparsers(dest="acao", required=True)
    criar = acoes.add_parser("criar-dono", help="cria um usuário dono")
    criar.add_argument("--login", required=True)
    criar.add_argument("--nome", required=True)
    criar.add_argument(
        "--outro-dono",
        action="store_true",
        help="cria mesmo que já exista um dono ativo",
    )
    pedido = leitor.parse_args(argumentos)

    senha = os.environ.get(VARIAVEL_DA_SENHA) or _senha_do_terminal()
    with get_sessionmaker()() as db:
        try:
            dono = criar_dono(db, pedido.login, pedido.nome, senha, outro_dono=pedido.outro_dono)
        except ValidationError as erro:
            sys.exit(_explicar(erro))
        except JaHaDono:
            sys.exit(
                "Já existe um dono ativo: ele cadastra os próximos usuários (POST /usuarios). "
                "Para criar outro dono mesmo assim, repita com --outro-dono."
            )
        except usuarios.LoginDuplicado:
            sys.exit(f"Já existe um usuário com o login {pedido.login.strip().lower()}.")
    print(f"Dono criado: {dono.nome} (login {dono.login}).")


def _senha_do_terminal() -> str:
    senha = getpass.getpass(f"Senha do dono (pelo menos {SENHA_MINIMA} caracteres): ")
    if getpass.getpass("Repita a senha: ") != senha:
        sys.exit("As senhas não conferem: nada foi criado.")
    return senha


def _explicar(erro: ValidationError) -> str:
    frases = {
        "login": "O login só pode ter letras sem acento, números, ponto, hífen e sublinhado "
        "(de 2 a 40).",
        "senha": f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres.",
        "nome": "Informe o nome do dono (até 120 caracteres).",
    }
    campos = dict.fromkeys(str(detalhe["loc"][0]) for detalhe in erro.errors())
    return " ".join(frases.get(campo, f"{campo} inválido.") for campo in campos)


if __name__ == "__main__":
    main()
